import json
import logging
import uuid
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.models.user import User
from app.models.payment import Payment
from app.schemas.payment import (
    CheckoutCreate, CheckoutResponse, PaymentResponse, PaymentVerifyResponse,
)
from app.api.deps import get_current_user
from app.services.payment import (
    APPROVED_STATUSES,
    FAILED_STATUSES,
    PLAN_PRICES,
    PaymentNotConfigured,
    compute_subscription_expiry,
    create_checkout,
    fetch_transaction,
    verify_webhook_signature,
)
from app.services.subscriptions import effective_plan
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


async def _apply_transaction_status(
    db: AsyncSession, payment: Payment, tx_status: str, tx_amount=None,
) -> None:
    """Applique le statut FedaPay (déjà vérifié) à *payment* — idempotent.

    La ligne *payment* doit être verrouillée (SELECT ... FOR UPDATE) par
    l'appelant: webhook et page de retour peuvent arriver en même temps.
    """
    if payment.status != "pending":
        return

    if tx_status in APPROVED_STATUSES:
        if tx_amount is not None:
            try:
                if int(tx_amount) != int(payment.amount):
                    logger.error(
                        "Payment %s amount mismatch: expected %s got %s — NOT activated",
                        payment.id, payment.amount, tx_amount,
                    )
                    payment.status = "failed"
                    return
            except (TypeError, ValueError):
                pass
        payment.status = "completed"
        user = (await db.execute(
            select(User).where(User.id == payment.user_id).with_for_update()
        )).scalar_one_or_none()
        if user:
            new_plan, expires_at = compute_subscription_expiry(user, payment.plan)
            user.plan = new_plan
            user.subscription_expires_at = expires_at
            logger.info(
                "User %s subscribed to %s until %s via payment %s",
                user.id, new_plan, expires_at, payment.id,
            )
    elif tx_status in FAILED_STATUSES:
        payment.status = "failed"
        logger.info("Payment %s failed: %s", payment.id, tx_status)


@router.post("/checkout", response_model=CheckoutResponse)
async def checkout(
    data: CheckoutCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if data.plan not in PLAN_PRICES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Plan invalide. Choisis « pro » ou « enterprise ».",
        )

    if data.currency not in ("XOF", "USD"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Devise invalide. Choisis XOF ou USD.",
        )

    # L'id du paiement est connu AVANT la transaction pour que FedaPay nous
    # renvoie dessus après le paiement (page /billing/return).
    payment_id = uuid.uuid4()
    callback_url = (
        f"{settings.PUBLIC_APP_URL.rstrip('/')}/billing/return?payment_id={payment_id}"
    )

    try:
        result = await create_checkout(
            plan=data.plan,
            currency=data.currency,
            user_email=current_user.email,
            callback_url=callback_url,
            full_name=current_user.full_name,
        )
    except PaymentNotConfigured:
        logger.error("Checkout requested but FEDAPAY_SECRET_KEY is not configured")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Le paiement en ligne n'est pas encore disponible. Contacte le support.",
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Payment provider error for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Le service de paiement est momentanément indisponible. Réessaie.",
        )

    payment = Payment(
        id=payment_id,
        user_id=current_user.id,
        fedapay_tx_id=result["tx_id"],
        amount=result["amount"],
        currency=data.currency,
        plan=data.plan,
    )
    db.add(payment)
    await db.flush()

    logger.info(f"Checkout created: payment={payment.id} plan={data.plan} user={current_user.id}")

    return CheckoutResponse(
        payment_id=payment.id,
        checkout_url=result["checkout_url"],
    )


@router.post("/{payment_id}/verify", response_model=PaymentVerifyResponse)
async def verify_payment(
    payment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Vérifie un paiement au retour de la page FedaPay.

    Filet de sécurité si le webhook est en retard ou mal configuré: on relit
    la transaction chez FedaPay et on active l'abonnement immédiatement.
    """
    payment = (await db.execute(
        select(Payment)
        .where(Payment.id == payment_id, Payment.user_id == current_user.id)
        .with_for_update()
    )).scalar_one_or_none()
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paiement introuvable")

    if payment.status == "pending" and payment.fedapay_tx_id:
        try:
            tx = await fetch_transaction(payment.fedapay_tx_id)
        except PaymentNotConfigured:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Le paiement en ligne n'est pas configuré.",
            )
        except (httpx.HTTPError, KeyError, ValueError) as e:
            logger.warning("Could not verify payment %s: %s", payment.id, e)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Vérification impossible pour le moment. Réessaie dans un instant.",
            )
        await _apply_transaction_status(db, payment, tx["status"], tx.get("amount"))
        await db.flush()
        await db.refresh(current_user)

    return PaymentVerifyResponse(
        id=payment.id,
        amount=payment.amount,
        currency=payment.currency,
        status=payment.status,
        plan=payment.plan,
        created_at=payment.created_at,
        effective_plan=effective_plan(current_user),
        subscription_expires_at=current_user.subscription_expires_at,
    )


@router.post("/webhook")
async def payment_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Handle FedaPay webhook callbacks.

    Sécurité:
      - Secret du webhook OBLIGATOIRE en production (sinon 503).
      - Signature ``X-FEDAPAY-SIGNATURE`` (t=…,s=…) vérifiée + anti-rejeu.
      - Le statut est RELU auprès de l'API FedaPay (jamais cru depuis le corps).
      - Idempotence: SELECT FOR UPDATE + statut déjà traité ignoré.
    """
    client_host = request.client.host if request.client else "unknown"
    secret = settings.FEDAPAY_WEBHOOK_SECRET or settings.FEDAPAY_SECRET_KEY

    if not secret:
        if settings.is_production:
            logger.error(
                "Webhook reçu mais aucun secret FedaPay configuré en production "
                "— webhook REJETÉ (from=%s)", client_host,
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Payment webhook is not configured.",
            )
        logger.warning("[dev] Webhook signature non vérifiée (aucun secret FedaPay)")

    raw_body = await request.body()
    try:
        body = json.loads(raw_body or b"{}")
        if not isinstance(body, dict):
            raise ValueError("not an object")
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON body")

    if secret:
        signature = request.headers.get("X-Fedapay-Signature", "")
        if not verify_webhook_signature(raw_body, signature, secret):
            logger.warning("Invalid webhook signature from %s", client_host)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid signature")

    entity = body.get("entity") or {}
    tx_id = str(entity.get("id") or "")
    if not tx_id:
        return {"status": "ignored"}

    # Lock pessimiste: webhook et page de retour peuvent arriver ensemble.
    payment = (await db.execute(
        select(Payment).where(Payment.fedapay_tx_id == tx_id).with_for_update()
    )).scalar_one_or_none()
    if not payment:
        logger.warning("Webhook for unknown transaction: %s", tx_id)
        return {"status": "not_found"}
    if payment.status != "pending":
        return {"status": "already_processed"}

    # Source de vérité: l'API FedaPay. Le corps du webhook ne sert qu'en dev
    # sans clé API.
    if settings.FEDAPAY_SECRET_KEY:
        try:
            tx = await fetch_transaction(tx_id)
        except Exception as e:  # noqa: BLE001 - FedaPay réessaiera le webhook
            logger.error("Webhook: cannot fetch transaction %s: %s", tx_id, e)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Transaction verification failed",
            )
        tx_status, tx_amount = tx["status"], tx.get("amount")
    else:
        tx_status, tx_amount = str(entity.get("status") or "").lower(), entity.get("amount")

    await _apply_transaction_status(db, payment, tx_status, tx_amount)
    return {"status": "processed"}


@router.get("/history", response_model=list[PaymentResponse])
async def payment_history(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get payment history for the current user."""
    result = await db.execute(
        select(Payment)
        .where(Payment.user_id == current_user.id)
        .order_by(Payment.created_at.desc())
    )
    return result.scalars().all()


@router.get("/plans")
async def get_plans():
    """Plans et limites RÉELLES (mêmes valeurs que celles appliquées par l'API)."""
    from app.services.plans import rules_for

    free, pro = rules_for("free"), rules_for("pro")
    days = settings.SUBSCRIPTION_PERIOD_DAYS
    return {
        "period_days": days,
        "plans": [
            {
                "id": "free",
                "name": "Gratuit",
                "price": {"XOF": 0, "USD": 0},
                "limits": {
                    "montages_per_month": free.max_videos_per_month,
                    "max_video_minutes": (free.max_video_duration_s or 0) // 60 or None,
                    "concurrent_jobs": free.max_concurrent_jobs,
                    "clips_per_job": free.clips_max_per_job,
                },
            },
            {
                "id": "pro",
                "name": "Pro",
                "price": PLAN_PRICES["pro"],
                "limits": {
                    "montages_per_month": None,
                    "max_video_minutes": (pro.max_video_duration_s or 0) // 60 or None,
                    "concurrent_jobs": pro.max_concurrent_jobs,
                    "clips_per_job": pro.clips_max_per_job,
                },
            },
            {
                "id": "enterprise",
                "name": "Enterprise",
                "price": PLAN_PRICES["enterprise"],
                "limits": {
                    "montages_per_month": None,
                    "max_video_minutes": None,
                    "concurrent_jobs": None,
                    "clips_per_job": rules_for("enterprise").clips_max_per_job,
                },
            },
        ],
    }
