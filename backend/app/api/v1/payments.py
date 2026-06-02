import hmac
import hashlib
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.models.user import User
from app.models.payment import Payment
from app.schemas.payment import CheckoutCreate, CheckoutResponse, PaymentResponse
from app.api.deps import get_current_user
from app.services.payment import create_checkout, PLAN_PRICES
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
            detail="Invalid plan. Choose 'pro' or 'enterprise'.",
        )

    if data.currency not in ("XOF", "USD"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid currency. Choose 'XOF' or 'USD'.",
        )

    try:
        result = await create_checkout(
            plan=data.plan,
            currency=data.currency,
            user_email=current_user.email,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Payment provider error for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Payment provider temporarily unavailable. Please try again.",
        )

    payment = Payment(
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


@router.post("/webhook")
async def payment_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Handle FedaPay webhook callbacks.

    Securite:
      - FEDAPAY_SECRET_KEY OBLIGATOIRE en production. Si la cle est absente,
        on rejette le webhook avec 503 plutot que d'upgrader un compte
        sans verification.
      - HMAC-SHA256 sur le corps brut.
      - Idempotence: SELECT FOR UPDATE + check du statut deja "completed".
    """
    client_host = request.client.host if request.client else "unknown"

    if not settings.FEDAPAY_SECRET_KEY:
        if settings.is_production:
            # Sans cle, n'importe qui peut upgrader des comptes. On refuse.
            logger.error(
                "Webhook recu mais FEDAPAY_SECRET_KEY absent en production "
                "— webhook REJETE (from=%s)", client_host,
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Payment webhook is not configured.",
            )
        logger.warning("[dev] Webhook signature non verifiee (FEDAPAY_SECRET_KEY absent)")

    raw_body = await request.body()
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON body",
        )

    # Verification de signature si cle presente
    if settings.FEDAPAY_SECRET_KEY:
        signature = request.headers.get("X-Fedapay-Signature", "")
        expected = hmac.HMAC(
            settings.FEDAPAY_SECRET_KEY.encode(),
            raw_body,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            logger.warning("Invalid webhook signature from %s", client_host)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Invalid signature"
            )

    entity = body.get("entity") or {}
    tx_id = str(entity.get("id") or "")
    tx_status = entity.get("status") or ""

    if not tx_id:
        return {"status": "ignored"}

    # Lock pessimiste pour eviter une race condition entre deux webhooks
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
        if tx_status == "approved":
            payment.status = "completed"
            user_result = await db.execute(
                select(User).where(User.id == payment.user_id)
            )
            user = user_result.scalar_one_or_none()
            if user:
                user.plan = payment.plan
                logger.info(
                    "User %s upgraded to %s via payment %s",
                    user.id, payment.plan, payment.id,
                )
        elif tx_status in ("declined", "cancelled"):
            payment.status = "failed"
            logger.info("Payment %s failed: %s", payment.id, tx_status)
    except Exception as e:
        logger.error("Webhook processing error for tx %s: %s", tx_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook processing failed",
        )

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
    """Get available subscription plans."""
    return {
        "plans": [
            {
                "id": "free",
                "name": "Free",
                "price": {"XOF": 0, "USD": 0},
                "features": [
                    f"{settings.MAX_VIDEOS_PER_MONTH_FREE} videos per month",
                    f"Max {settings.MAX_VIDEO_DURATION_FREE // 60} min video",
                    "Basic editing",
                    "720p export",
                ],
            },
            {
                "id": "pro",
                "name": "Pro",
                "price": {"XOF": 5000, "USD": 10},
                "features": [
                    "Unlimited videos",
                    f"Max {settings.MAX_VIDEO_DURATION_PRO // 60} min video",
                    "AI editing modes",
                    "1080p export",
                    "Subtitle generation",
                    "Priority processing",
                ],
            },
            {
                "id": "enterprise",
                "name": "Enterprise",
                "price": {"XOF": 15000, "USD": 30},
                "features": [
                    "Unlimited everything",
                    "No duration limit",
                    "All AI modes",
                    "4K export",
                    "Custom branding",
                    "API access",
                    "Dedicated support",
                ],
            },
        ]
    }
