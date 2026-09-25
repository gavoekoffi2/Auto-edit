"""Paiements FedaPay: signature webhook, activation d'abonnement, idempotence."""
import asyncio
import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.config import settings
from app.services.payment import (
    apply_paid_subscription,
    transaction_matches_payment,
    verify_webhook_signature,
)

NOW = datetime(2026, 9, 1, tzinfo=timezone.utc)


def _sign(body: bytes, secret: str, ts: int) -> str:
    sig = hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    return f"t={ts},s={sig}"


def test_webhook_signature_valid():
    body = b'{"entity":{"id":42}}'
    header = _sign(body, "wh_secret", 1_000_000)
    assert verify_webhook_signature(body, header, "wh_secret", now=1_000_010)


def test_webhook_signature_rejects_tampered_body_wrong_secret_and_replay():
    body = b'{"entity":{"id":42}}'
    header = _sign(body, "wh_secret", 1_000_000)
    assert not verify_webhook_signature(b'{"entity":{"id":43}}', header, "wh_secret", now=1_000_000)
    assert not verify_webhook_signature(body, header, "other", now=1_000_000)
    assert not verify_webhook_signature(body, header, "wh_secret", now=1_000_000 + 3600)
    assert not verify_webhook_signature(body, "", "wh_secret", now=1_000_000)
    assert not verify_webhook_signature(body, "garbage", "wh_secret", now=1_000_000)


def _user(**kw):
    data = {"plan": "free", "subscription_expires_at": None}
    data.update(kw)
    return SimpleNamespace(**data)


def test_first_payment_grants_limited_subscription_not_lifetime():
    user = _user()
    apply_paid_subscription(user, "pro", now=NOW)
    assert user.plan == "pro"
    assert user.subscription_expires_at == NOW + timedelta(days=settings.SUBSCRIPTION_DAYS)


def test_early_renewal_extends_from_current_expiry():
    expiry = NOW + timedelta(days=10)
    user = _user(plan="pro", subscription_expires_at=expiry)
    apply_paid_subscription(user, "pro", now=NOW)
    assert user.subscription_expires_at == expiry + timedelta(days=settings.SUBSCRIPTION_DAYS)


def test_expired_subscription_restarts_from_now():
    user = _user(plan="pro", subscription_expires_at=NOW - timedelta(days=3))
    apply_paid_subscription(user, "pro", now=NOW)
    assert user.subscription_expires_at == NOW + timedelta(days=settings.SUBSCRIPTION_DAYS)


def test_buying_pro_never_downgrades_active_enterprise():
    user = _user(plan="enterprise", subscription_expires_at=NOW + timedelta(days=5))
    apply_paid_subscription(user, "pro", now=NOW)
    assert user.plan == "enterprise"


def test_permanent_access_is_kept():
    user = _user(plan="pro", subscription_expires_at=None)
    apply_paid_subscription(user, "pro", now=NOW)
    assert user.subscription_expires_at is None
    apply_paid_subscription(user, "enterprise", now=NOW)
    assert user.plan == "enterprise" and user.subscription_expires_at is None


def test_transaction_amount_must_match():
    payment = SimpleNamespace(amount=5000, currency="XOF")
    assert transaction_matches_payment({"amount": 5000, "currency": {"iso": "XOF"}}, payment)
    assert not transaction_matches_payment({"amount": 100, "currency": {"iso": "XOF"}}, payment)
    assert not transaction_matches_payment({"amount": 5000, "currency": {"iso": "USD"}}, payment)


class _FakeResult:
    def __init__(self, obj):
        self._obj = obj

    def scalar_one_or_none(self):
        return self._obj


class _FakeDB:
    def __init__(self, user):
        self.user = user

    async def execute(self, *_a, **_k):
        return _FakeResult(self.user)

    async def flush(self):
        return None


def test_apply_transaction_is_idempotent():
    from app.services.payment import apply_transaction as _apply_transaction

    user = _user()
    payment = SimpleNamespace(id="p1", user_id="u1", amount=5000, currency="XOF",
                              plan="pro", status="pending")
    db = _FakeDB(user)
    tx = {"id": 1, "status": "approved", "amount": 5000, "currency": {"iso": "XOF"}}

    assert asyncio.run(_apply_transaction(db, payment, tx)) == "completed"
    first_expiry = user.subscription_expires_at
    assert payment.status == "completed" and user.plan == "pro"
    # Webhook + retour navigateur simultanés: jamais de double prolongation.
    assert asyncio.run(_apply_transaction(db, payment, tx)) == "already_processed"
    assert user.subscription_expires_at == first_expiry


def test_apply_transaction_declined_and_pending():
    from app.services.payment import apply_transaction as _apply_transaction

    user = _user()
    db = _FakeDB(user)
    p = SimpleNamespace(id="p", user_id="u", amount=5000, currency="XOF", plan="pro", status="pending")
    assert asyncio.run(_apply_transaction(db, p, {"status": "pending"})) == "pending"
    assert p.status == "pending"
    assert asyncio.run(_apply_transaction(db, p, {"status": "declined"})) == "failed"
    assert p.status == "failed" and user.plan == "free"
