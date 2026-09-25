import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.models.user import User
from app.models.payment import Payment
from app.schemas.payment import CheckoutCreate, CheckoutResponse, PaymentResponse
from app.api.deps import get_current_user
from app.services.payment import (
    PLAN_PRICES,
    PaymentProviderError,
    apply_transaction as _apply_transaction,
    create_checkout,
    fetch_transaction,
    verify_webhook_signature,
)
from app.services.rate_limiter import check_rate_limit
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/checkout", response_model=CheckoutResponse)
async def checkout(
    data: CheckoutCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if data.plan not in PLAN_PRICES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Plan invalide. Choisis 'pro' ou 'enterprise'.",
        )

    if data.currency not in ("XOF", "USD"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Devise invalide. Choisis 'XOF' ou 'USD'.",
        )

    if not settings.FEDAPAY_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Le paiement en ligne n'est pas encore activé. Contacte le support.",
        )

    await check_rate_limit(f"checkout:{current_user.id}", max_attempts=10, window_seconds=3600)

    # La ligne Payment est créée AVANT la transaction pour que l'URL de retour
    # porte son id: le frontend peut alors faire vérifier le paiement au
    # retour, même si le webhook FedaPay n'arrive jamais.
    payment = Payment(
        user_id=current_user.id,
        amount=PLAN_PRICES[data.plan][data.currency],
        currency=data.currency,
        plan=data.plan,
    )
    db.add(payment)
    await db.flush()

    callback_url = f"{settings.PUBLIC_APP_URL.rstrip('/')}/dashboard?payment={payment.id}"
    try:
        result = await create_checkout(
            plan=data.plan,
            currency=data.currency,
            user_email=current_user.email,
            callback_url=callback_url,
            full_name=current_user.full_name,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Payment provider error for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Le service de paiement est momentanément indisponible. Réessaie.",
        )

    payment.fedapay_tx_id = result["tx_id"]
    payment.amount = result["amount"]
    await db.flush()

    logger.info(f"Checkout created: payment={payment.id} plan={data.plan} user={current_user.id}")

    return CheckoutResponse(
        payment_id=payment.id,
        checkout_url=result["checkout_url"],
    )


@router.post("/{payment_id}/verify", response_model=PaymentResponse)
async def verify_payment(
    payment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Revérifie un paiement auprès de FedaPay (appelé au retour du checkout).

    Filet de sécurité indispensable: si le webhook est mal configuré, bloqué
    ou en retard, l'utilisateur qui vient de payer est quand même activé.
    """
    payment = (await db.execute(
        select(Payment)
        .where(Payment.id == payment_id, Payment.user_id == current_user.id)
        .with_for_update()
    )).scalar_one_or_none()
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paiement introuvable")

    if payment.status == "pending" and payment.fedapay_tx_id:
        await check_rate_limit(f"verify:{current_user.id}", max_attempts=60, window_seconds=3600)
        try:
            tx = await fetch_transaction(payment.fedapay_tx_id)
        except Exception as e:
            logger.warning("verify_payment %s: FedaPay indisponible: %s", payment.id, e)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Impossible de vérifier le paiement pour l'instant. Réessaie dans un instant.",
            )
        await _apply_transaction(db, payment, tx)
    return payment


@router.post("/webhook")
async def payment_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Webhook FedaPay.

    Sécurité:
      - Signature ``X-FEDAPAY-SIGNATURE`` vérifiée si FEDAPAY_WEBHOOK_SECRET
        est configuré.
      - Le corps n'est qu'un indice: le statut est TOUJOURS relu auprès de
        l'API FedaPay (clé secrète) avant d'activer quoi que ce soit.
      - Idempotence: SELECT FOR UPDATE + paiement déjà `completed` ignoré.
    """
    client_host = request.client.host if request.client else "unknown"

    if not settings.FEDAPAY_SECRET_KEY:
        logger.error("Webhook reçu mais FEDAPAY_SECRET_KEY absent — rejeté (from=%s)", client_host)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Payment webhook is not configured.",
        )

    raw_body = await request.body()

    if settings.FEDAPAY_WEBHOOK_SECRET:
        signature = request.headers.get("x-fedapay-signature", "")
        if not verify_webhook_signature(raw_body, signature, settings.FEDAPAY_WEBHOOK_SECRET):
            logger.warning("Invalid webhook signature from %s", client_host)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid signature")

    try:
        import json
        body = json.loads(raw_body or b"{}")
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON body")

    entity = body.get("entity") if isinstance(body, dict) else None
    tx_id = str((entity or {}).get("id") or "") if isinstance(entity, dict) else ""
    if not tx_id:
        return {"status": "ignored"}

    result = await db.execute(
        select(Payment).where(Payment.fedapay_tx_id == tx_id).with_for_update()
    )
    payment = result.scalar_one_or_none()
    if not payment:
        logger.warning("Webhook for unknown transaction: %s", tx_id)
        return {"status": "not_found"}

    if payment.status == "completed":
        return {"status": "already_processed"}

    try:
        tx = await fetch_transaction(tx_id)
    except (PaymentProviderError, Exception) as e:
        # 5xx => FedaPay re-livrera le webhook plus tard.
        logger.error("Webhook tx %s: vérification FedaPay impossible: %s", tx_id, e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not verify transaction",
        )

    outcome = await _apply_transaction(db, payment, tx)
    return {"status": outcome}


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
        .limit(100)
    )
    return result.scalars().all()


@router.get("/plans")
async def get_plans():
    """Plans d'abonnement — reflète EXACTEMENT les quotas appliqués par le backend."""
    free_min = settings.MAX_VIDEO_DURATION_FREE // 60
    pro_min = settings.MAX_VIDEO_DURATION_PRO // 60
    days = settings.SUBSCRIPTION_DAYS
    return {
        "payments_enabled": bool(settings.FEDAPAY_SECRET_KEY),
        "subscription_days": days,
        "plans": [
            {
                "id": "free",
                "name": "Free",
                "price": {"XOF": 0, "USD": 0},
                "features": [
                    f"{settings.MAX_VIDEOS_PER_MONTH_FREE} vidéos / mois",
                    f"{free_min} min max par vidéo",
                    "Tous les styles de montage",
                    f"Clips : {settings.CLIPS_MAX_PER_JOB_FREE} shorts par vidéo longue",
                    "2 montages en parallèle",
                ],
            },
            {
                "id": "pro",
                "name": "Pro",
                "price": PLAN_PRICES["pro"],
                "features": [
                    "Vidéos illimitées",
                    f"{pro_min} min max par vidéo",
                    "Tous les styles + B-roll IA",
                    f"Clips : {settings.CLIPS_MAX_PER_JOB_PRO} shorts par vidéo longue",
                    "5 montages en parallèle",
                    "Support prioritaire",
                ],
            },
            {
                "id": "enterprise",
                "name": "Enterprise",
                "price": PLAN_PRICES["enterprise"],
                "features": [
                    "Vidéos illimitées",
                    "Aucune limite de durée",
                    "Tous les styles + B-roll IA",
                    "Clips : jusqu'à 100 shorts par vidéo",
                    "Montages en parallèle illimités",
                    "Support dédié",
                ],
            },
        ],
    }
