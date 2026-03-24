import httpx
from typing import Optional

from app.config import settings

PLAN_PRICES = {
    "pro": {"XOF": 5000, "USD": 10},
    "enterprise": {"XOF": 15000, "USD": 30},
}

FEDAPAY_API_URL = (
    "https://sandbox-api.fedapay.com" if settings.FEDAPAY_ENV == "sandbox"
    else "https://api.fedapay.com"
)


async def create_checkout(
    plan: str, currency: str, user_email: str, callback_url: Optional[str] = None
) -> dict:
    """Create a FedaPay transaction and return checkout URL."""
    amount = PLAN_PRICES.get(plan, {}).get(currency, 0)
    if amount == 0:
        raise ValueError(f"Invalid plan '{plan}' or currency '{currency}'")

    headers = {
        "Authorization": f"Bearer {settings.FEDAPAY_SECRET_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "description": f"AutoEdit {plan.title()} Plan",
        "amount": amount,
        "currency": {"iso": currency},
        "callback_url": callback_url or "",
        "customer": {"email": user_email},
    }

    async with httpx.AsyncClient() as client:
        # Create transaction
        resp = await client.post(
            f"{FEDAPAY_API_URL}/v1/transactions",
            json=payload,
            headers=headers,
        )
        resp.raise_for_status()
        tx_data = resp.json()
        tx_id = tx_data["v1/transaction"]["id"]

        # Generate payment token/URL
        token_resp = await client.post(
            f"{FEDAPAY_API_URL}/v1/transactions/{tx_id}/token",
            headers=headers,
        )
        token_resp.raise_for_status()
        token_data = token_resp.json()

        return {
            "tx_id": str(tx_id),
            "checkout_url": token_data.get("token", ""),
            "amount": amount,
        }
