from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional


class CheckoutCreate(BaseModel):
    plan: str  # pro, enterprise
    currency: str = "XOF"


class CheckoutResponse(BaseModel):
    payment_id: UUID
    checkout_url: str


class PaymentResponse(BaseModel):
    id: UUID
    amount: int
    currency: str
    status: str
    plan: str
    created_at: datetime

    model_config = {"from_attributes": True}
