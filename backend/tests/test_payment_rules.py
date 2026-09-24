"""Règles d'abonnement, signature webhook FedaPay et messages d'échec."""
import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.services.payment import compute_subscription_expiry, verify_webhook_signature

NOW = datetime(2026, 9, 1, tzinfo=timezone.utc)


def _user(plan="free", expires=None):
    return SimpleNamespace(plan=plan, subscription_expires_at=expires)


def test_first_payment_gives_30_days():
    plan, exp = compute_subscription_expiry(_user(), "pro", now=NOW)
    assert plan == "pro" and exp == NOW + timedelta(days=30)


def test_early_renewal_extends_remaining_time():
    plan, exp = compute_subscription_expiry(
        _user("pro", NOW + timedelta(days=10)), "pro", now=NOW)
    assert exp == NOW + timedelta(days=40)


def test_expired_subscription_restarts_from_now():
    _, exp = compute_subscription_expiry(_user("pro", NOW - timedelta(days=5)), "pro", now=NOW)
    assert exp == NOW + timedelta(days=30)


def test_permanent_admin_grant_is_never_downgraded():
    plan, exp = compute_subscription_expiry(_user("enterprise", None), "pro", now=NOW)
    assert plan == "enterprise" and exp is None


def test_upgrade_from_permanent_pro_to_enterprise_is_applied():
    plan, exp = compute_subscription_expiry(_user("pro", None), "enterprise", now=NOW)
    assert plan == "enterprise" and exp == NOW + timedelta(days=30)


def test_signature_formats():
    body = b'{"entity":{"id":1}}'
    ts = 1_700_000_000
    sig = hmac.new(b"wh", f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    assert verify_webhook_signature(body, f"t={ts},s={sig}", "wh", now=ts + 10)
    assert not verify_webhook_signature(body, f"t={ts},s={sig}", "wh", now=ts + 3600)
    assert not verify_webhook_signature(body + b" ", f"t={ts},s={sig}", "wh", now=ts)
    assert not verify_webhook_signature(body, "", "wh")
    legacy = hmac.new(b"wh", body, hashlib.sha256).hexdigest()
    assert verify_webhook_signature(body, legacy, "wh")


def test_worker_error_messages_hide_internals():
    from app.workers.tasks import _user_error_message

    coded = _user_error_message(RuntimeError("[NO_SPEECH] Aucune parole"))
    assert coded.startswith("[NO_SPEECH]")
    raw = _user_error_message(RuntimeError("Command '['ffmpeg', '-i', '/app/uploads/x']' returned 1"))
    assert raw.startswith("[RENDER_FAILED]") and "/app/uploads" not in raw
