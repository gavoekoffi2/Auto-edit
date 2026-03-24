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
    """Handle FedaPay webhook callbacks with signature verification."""
    raw_body = await request.body()
    body = await request.json()

    # Verify webhook signature if secret key is configured
    if settings.FEDAPAY_SECRET_KEY:
        signature = request.headers.get("X-Fedapay-Signature", "")
        expected = hmac.new(
            settings.FEDAPAY_SECRET_KEY.encode(),
            raw_body,
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(signature, expected):
            logger.warning(f"Invalid webhook signature from {request.client.host if request.client else 'unknown'}")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid signature")

    entity = body.get("entity", {})
    tx_id = str(entity.get("id", ""))
    tx_status = entity.get("status", "")

    if not tx_id:
        return {"status": "ignored"}

    result = await db.execute(
        select(Payment).where(Payment.fedapay_tx_id == tx_id)
    )
    payment = result.scalar_one_or_none()
    if not payment:
        logger.warning(f"Webhook for unknown transaction: {tx_id}")
        return {"status": "not_found"}

    # Prevent duplicate processing
    if payment.status == "completed":
        return {"status": "already_processed"}

    if tx_status == "approved":
        payment.status = "completed"

        # Upgrade user plan
        user_result = await db.execute(
            select(User).where(User.id == payment.user_id)
        )
        user = user_result.scalar_one_or_none()
        if user:
            user.plan = payment.plan
            logger.info(f"User {user.id} upgraded to {payment.plan} via payment {payment.id}")

    elif tx_status in ("declined", "cancelled"):
        payment.status = "failed"
        logger.info(f"Payment {payment.id} failed: {tx_status}")

    return {"status": "processed"}


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
