from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.models.user import User
from app.models.payment import Payment
from app.schemas.payment import CheckoutCreate, CheckoutResponse, PaymentResponse
from app.api.deps import get_current_user
from app.services.payment import create_checkout, PLAN_PRICES

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
            detail="Invalid plan",
        )

    try:
        result = await create_checkout(
            plan=data.plan,
            currency=data.currency,
            user_email=current_user.email,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Payment provider error: {str(e)}",
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

    return CheckoutResponse(
        payment_id=payment.id,
        checkout_url=result["checkout_url"],
    )


@router.post("/webhook")
async def payment_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Handle FedaPay webhook callbacks."""
    body = await request.json()

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
        return {"status": "not_found"}

    if tx_status == "approved":
        payment.status = "completed"

        # Upgrade user plan
        user_result = await db.execute(
            select(User).where(User.id == payment.user_id)
        )
        user = user_result.scalar_one_or_none()
        if user:
            user.plan = payment.plan
    elif tx_status in ("declined", "cancelled"):
        payment.status = "failed"

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
                    "2 videos per month",
                    "Max 5 min video",
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
                    "Max 30 min video",
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
