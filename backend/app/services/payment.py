"""Paiement FedaPay (Mobile Money / carte) — client HTTP + règles d'abonnement.

Principes:
  * Le statut d'une transaction n'est JAMAIS cru sur parole depuis le corps
    d'un webhook ou l'URL de retour: on le relit auprès de l'API FedaPay
    (source de vérité) avant d'activer quoi que ce soit.
  * Un paiement réussi donne ``SUBSCRIPTION_PERIOD_DAYS`` jours d'abonnement
    (prolongés si l'abonnement au même plan est encore actif). Avant, le
    webhook passait le compte en Pro SANS date d'expiration: un seul
    paiement mensuel donnait un accès à vie.
"""
from __future__ import annotations

import hashlib
import hmac
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

from app.config import settings

PLAN_PRICES = {
    "pro": {"XOF": 5000, "USD": 10},
    "enterprise": {"XOF": 15000, "USD": 30},
}

PLAN_RANK = {"free": 0, "pro": 1, "enterprise": 2}

# Statuts FedaPay -> statut de notre ligne Payment.
APPROVED_STATUSES = {"approved", "transferred"}
FAILED_STATUSES = {"declined", "canceled", "cancelled", "expired", "refunded"}

# Fenêtre de tolérance de l'horodatage signé des webhooks (anti-rejeu).
WEBHOOK_TOLERANCE_S = 300


class PaymentNotConfigured(RuntimeError):
    """FEDAPAY_SECRET_KEY absent: impossible d'encaisser."""


def _api_base() -> str:
    return (
        "https://sandbox-api.fedapay.com" if settings.FEDAPAY_ENV == "sandbox"
        else "https://api.fedapay.com"
    )


def _checkout_base() -> str:
    return (
        "https://sandbox-process.fedapay.com" if settings.FEDAPAY_ENV == "sandbox"
        else "https://process.fedapay.com"
    )


def _headers() -> dict:
    if not settings.FEDAPAY_SECRET_KEY:
        raise PaymentNotConfigured("FEDAPAY_SECRET_KEY missing")
    return {
        "Authorization": f"Bearer {settings.FEDAPAY_SECRET_KEY}",
        "Content-Type": "application/json",
    }


def _split_name(full_name: str | None) -> tuple[str, str]:
    parts = (full_name or "").strip().split()
    if not parts:
        return "Client", "CutForge"
    if len(parts) == 1:
        return parts[0], parts[0]
    return parts[0], " ".join(parts[1:])


def _tx_from_response(data: dict) -> dict:
    """L'API FedaPay enveloppe l'objet sous la clé ``v1/transaction``."""
    return data.get("v1/transaction") or data.get("transaction") or data


async def create_checkout(
    plan: str,
    currency: str,
    user_email: str,
    callback_url: Optional[str] = None,
    full_name: Optional[str] = None,
) -> dict:
    """Crée une transaction FedaPay et renvoie l'URL de la page de paiement."""
    amount = PLAN_PRICES.get(plan, {}).get(currency, 0)
    if amount == 0:
        raise ValueError(f"Invalid plan '{plan}' or currency '{currency}'")

    headers = _headers()
    firstname, lastname = _split_name(full_name)
    payload = {
        "description": f"CutForge {plan.title()} — {settings.SUBSCRIPTION_PERIOD_DAYS} jours",
        "amount": amount,
        "currency": {"iso": currency},
        "callback_url": callback_url or "",
        "customer": {"email": user_email, "firstname": firstname, "lastname": lastname},
    }

    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
        resp = await client.post(f"{_api_base()}/v1/transactions", json=payload, headers=headers)
        resp.raise_for_status()
        tx_id = _tx_from_response(resp.json())["id"]

        token_resp = await client.post(
            f"{_api_base()}/v1/transactions/{tx_id}/token", headers=headers
        )
        token_resp.raise_for_status()
        token_data = token_resp.json()

    # L'endpoint /token renvoie {"token": "...", "url": "https://process..."}.
    # L'ancien code renvoyait le TOKEN brut comme URL: la redirection vers la
    # page de paiement ne pouvait pas fonctionner.
    checkout_url = token_data.get("url")
    if not checkout_url and token_data.get("token"):
        checkout_url = f"{_checkout_base()}/{token_data['token']}"
    if not checkout_url:
        raise RuntimeError("FedaPay did not return a checkout URL")

    return {"tx_id": str(tx_id), "checkout_url": checkout_url, "amount": amount}


async def fetch_transaction(tx_id: str) -> dict:
    """Relit une transaction auprès de FedaPay: {"status": ..., "amount": ...}."""
    async with httpx.AsyncClient(timeout=httpx.Timeout(20.0)) as client:
        resp = await client.get(f"{_api_base()}/v1/transactions/{tx_id}", headers=_headers())
        resp.raise_for_status()
        tx = _tx_from_response(resp.json())
    return {"status": str(tx.get("status") or "").lower(), "amount": tx.get("amount")}


def verify_webhook_signature(
    raw_body: bytes, header: str, secret: str, *, now: float | None = None,
) -> bool:
    """Vérifie l'en-tête ``X-FEDAPAY-SIGNATURE``.

    Format FedaPay (même schéma que Stripe): ``t=<timestamp>,s=<hex>`` où
    ``s = HMAC-SHA256(secret, "<t>.<corps brut>")``. L'horodatage doit être
    récent (anti-rejeu). Un en-tête hexadécimal nu (HMAC du corps seul) est
    encore accepté pour compatibilité avec l'ancienne intégration.
    """
    if not header or not secret:
        return False
    header = header.strip()

    if "=" not in header:
        expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(header, expected)

    timestamp = None
    signatures: list[str] = []
    for item in header.split(","):
        key, _, value = item.strip().partition("=")
        if key == "t":
            timestamp = value
        elif key == "s":
            signatures.append(value)
    if not timestamp or not signatures:
        return False
    try:
        ts = int(timestamp)
    except ValueError:
        return False
    current = time.time() if now is None else now
    if abs(current - ts) > WEBHOOK_TOLERANCE_S:
        return False

    signed = f"{timestamp}.".encode() + raw_body
    expected = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(sig, expected) for sig in signatures)


def compute_subscription_expiry(user, plan: str, *, now: datetime | None = None) -> tuple[str, datetime | None]:
    """(plan, date d'expiration) après un paiement réussi pour *plan*.

    * Même plan encore actif -> la période est AJOUTÉE à la date actuelle
      (renouvellement anticipé sans perte de jours).
    * Accès permanent (expiration NULL, accordé par un admin) à un plan
      supérieur ou égal -> conservé tel quel, on ne le dégrade pas.
    * Sinon -> maintenant + période.
    """
    now = now or datetime.now(timezone.utc)
    period = timedelta(days=settings.SUBSCRIPTION_PERIOD_DAYS)
    current_plan = getattr(user, "plan", "free") or "free"
    expires = getattr(user, "subscription_expires_at", None)
    if expires is not None and expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)

    if current_plan != "free" and expires is None and PLAN_RANK.get(current_plan, 0) >= PLAN_RANK.get(plan, 0):
        return current_plan, None
    if current_plan == plan and expires is not None and expires > now:
        return plan, expires + period
    return plan, now + period
