"""Intégration FedaPay (Mobile Money / carte) + activation d'abonnement.

Principes de sécurité:
  * Le statut d'une transaction n'est JAMAIS lu dans le corps d'un webhook ni
    dans les paramètres de retour du navigateur: on le relit toujours auprès de
    l'API FedaPay avec la clé secrète (source de vérité). Le webhook ne sert
    qu'à nous dire « regarde cette transaction ».
  * La signature webhook (en-tête ``X-FEDAPAY-SIGNATURE: t=<ts>,s=<hmac>``,
    HMAC-SHA256 de ``"<ts>.<corps brut>"`` avec le secret de l'endpoint) est
    vérifiée quand ``FEDAPAY_WEBHOOK_SECRET`` est configuré.
  * Un paiement = ``SUBSCRIPTION_DAYS`` jours d'abonnement (cumulables).
"""
from __future__ import annotations

import hashlib
import hmac
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

PLAN_PRICES = {
    "pro": {"XOF": 5000, "USD": 10},
    "enterprise": {"XOF": 15000, "USD": 30},
}

# Rang des plans: un achat ne doit jamais rétrograder un plan supérieur actif.
PLAN_RANK = {"free": 0, "pro": 1, "enterprise": 2}

# Tolérance d'horloge sur l'horodatage signé du webhook (anti-rejeu).
WEBHOOK_TOLERANCE_S = 600


class PaymentProviderError(RuntimeError):
    """Réponse inattendue / indisponibilité de FedaPay."""


def _api_url() -> str:
    return (
        "https://sandbox-api.fedapay.com" if settings.FEDAPAY_ENV == "sandbox"
        else "https://api.fedapay.com"
    )


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.FEDAPAY_SECRET_KEY}",
        "Content-Type": "application/json",
    }


def _unwrap_transaction(data: dict) -> dict:
    """FedaPay enveloppe l'objet sous la clé ``v1/transaction``."""
    if not isinstance(data, dict):
        raise PaymentProviderError("réponse FedaPay invalide")
    tx = data.get("v1/transaction") or data.get("transaction") or data
    if not isinstance(tx, dict) or "id" not in tx:
        raise PaymentProviderError("transaction absente de la réponse FedaPay")
    return tx


async def create_checkout(
    plan: str, currency: str, user_email: str, callback_url: Optional[str] = None,
    full_name: Optional[str] = None,
) -> dict:
    """Crée une transaction FedaPay et renvoie l'URL de paiement hébergée."""
    amount = PLAN_PRICES.get(plan, {}).get(currency, 0)
    if amount == 0:
        raise ValueError(f"Invalid plan '{plan}' or currency '{currency}'")
    if not settings.FEDAPAY_SECRET_KEY:
        raise PaymentProviderError("FEDAPAY_SECRET_KEY non configurée")

    customer: dict = {"email": user_email}
    if full_name:
        parts = full_name.strip().split(" ", 1)
        customer["firstname"] = parts[0][:100]
        if len(parts) > 1:
            customer["lastname"] = parts[1][:100]

    payload = {
        "description": f"CutForge {plan.title()} — {settings.SUBSCRIPTION_DAYS} jours",
        "amount": amount,
        "currency": {"iso": currency},
        "callback_url": callback_url or "",
        "customer": customer,
    }

    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
        resp = await client.post(
            f"{_api_url()}/v1/transactions", json=payload, headers=_headers())
        resp.raise_for_status()
        tx = _unwrap_transaction(resp.json())
        tx_id = tx["id"]

        token_resp = await client.post(
            f"{_api_url()}/v1/transactions/{tx_id}/token", headers=_headers())
        token_resp.raise_for_status()
        token_data = token_resp.json() or {}

    # L'URL de paiement est `url`. `token` seul n'est PAS une URL: rediriger
    # le navigateur dessus menait à une page 404.
    checkout_url = token_data.get("url") or ""
    if not checkout_url and token_data.get("token"):
        host = ("https://sandbox-process.fedapay.com" if settings.FEDAPAY_ENV == "sandbox"
                else "https://process.fedapay.com")
        checkout_url = f"{host}/{token_data['token']}"
    if not checkout_url:
        raise PaymentProviderError("URL de paiement absente de la réponse FedaPay")

    return {"tx_id": str(tx_id), "checkout_url": checkout_url, "amount": amount}


async def fetch_transaction(tx_id: str) -> dict:
    """Relit une transaction auprès de FedaPay (source de vérité du statut)."""
    if not settings.FEDAPAY_SECRET_KEY:
        raise PaymentProviderError("FEDAPAY_SECRET_KEY non configurée")
    async with httpx.AsyncClient(timeout=httpx.Timeout(20.0)) as client:
        resp = await client.get(
            f"{_api_url()}/v1/transactions/{tx_id}", headers=_headers())
        resp.raise_for_status()
        return _unwrap_transaction(resp.json())


def verify_webhook_signature(raw_body: bytes, header: str, secret: str,
                             now: Optional[float] = None) -> bool:
    """Vérifie ``X-FEDAPAY-SIGNATURE: t=<timestamp>,s=<signature>``."""
    if not header or not secret:
        return False
    parts: dict[str, list[str]] = {}
    for item in header.split(","):
        if "=" in item:
            k, v = item.split("=", 1)
            parts.setdefault(k.strip(), []).append(v.strip())
    try:
        ts = int(parts.get("t", [""])[0])
    except ValueError:
        return False
    current = time.time() if now is None else now
    if abs(current - ts) > WEBHOOK_TOLERANCE_S:
        return False
    signed = f"{ts}.".encode() + raw_body
    expected = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(expected, s) for s in parts.get("s", []))


def transaction_matches_payment(tx: dict, payment) -> bool:
    """Le montant/la devise payés correspondent-ils au paiement attendu ?"""
    try:
        amount_ok = int(tx.get("amount") or 0) >= int(payment.amount)
    except (TypeError, ValueError):
        return False
    cur = tx.get("currency")
    iso = None
    if isinstance(cur, dict):
        iso = cur.get("iso")
    elif isinstance(cur, str):
        iso = cur
    currency_ok = iso is None or str(iso).upper() == str(payment.currency).upper()
    return amount_ok and currency_ok


def _aware(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def apply_paid_subscription(user, plan: str, now: Optional[datetime] = None) -> None:
    """Active/prolonge l'abonnement de *user* après un paiement validé.

    * Chaque paiement ajoute ``SUBSCRIPTION_DAYS`` jours, à partir de la fin
      de l'abonnement en cours s'il est encore actif (pas de jours perdus en
      renouvelant en avance).
    * Un plan supérieur actif n'est jamais rétrogradé.
    * Un accès permanent (expiration NULL, accordé par un admin) reste permanent.
    """
    now = now or datetime.now(timezone.utc)
    current_plan = getattr(user, "plan", "free") or "free"
    expires = _aware(getattr(user, "subscription_expires_at", None))

    if current_plan != "free" and expires is None:
        # Accès permanent: on ne raccourcit rien, on n'upgrade que si mieux.
        if PLAN_RANK.get(plan, 0) > PLAN_RANK.get(current_plan, 0):
            user.plan = plan
        return

    active = current_plan != "free" and expires is not None and expires > now
    base = expires if active else now
    if active and PLAN_RANK.get(current_plan, 0) > PLAN_RANK.get(plan, 0):
        new_plan = current_plan
    else:
        new_plan = plan
    user.plan = new_plan
    user.subscription_expires_at = base + timedelta(days=settings.SUBSCRIPTION_DAYS)


# Statuts FedaPay terminaux.
_APPROVED = {"approved", "transferred"}
_FAILED = {"declined", "canceled", "cancelled", "refunded", "expired"}


async def apply_transaction(db, payment, tx: dict) -> str:
    """Applique le statut *vérifié auprès de FedaPay* à un paiement verrouillé.

    Idempotent: un paiement déjà `completed` n'est jamais ré-appliqué (pas de
    double prolongation si webhook + retour navigateur arrivent ensemble —
    l'appelant tient un verrou FOR UPDATE sur la ligne du paiement).
    """
    from sqlalchemy import select
    from app.models.user import User

    if payment.status == "completed":
        return "already_processed"

    tx_status = str(tx.get("status") or "").lower()
    if tx_status in _APPROVED:
        if not transaction_matches_payment(tx, payment):
            logger.error(
                "Payment %s: montant/devise FedaPay incohérents (tx=%s amount=%s) — refusé",
                payment.id, tx.get("id"), tx.get("amount"),
            )
            payment.status = "failed"
            await db.flush()
            return "amount_mismatch"
        user = (await db.execute(
            select(User).where(User.id == payment.user_id).with_for_update()
        )).scalar_one_or_none()
        payment.status = "completed"
        if user:
            apply_paid_subscription(user, payment.plan)
            logger.info("User %s -> %s jusqu'au %s (payment %s)",
                        user.id if hasattr(user, "id") else "?", user.plan,
                        user.subscription_expires_at, payment.id)
        await db.flush()
        return "completed"
    if tx_status in _FAILED:
        payment.status = "failed"
        await db.flush()
        return "failed"
    return "pending"
