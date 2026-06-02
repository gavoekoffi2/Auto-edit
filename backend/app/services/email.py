"""Service email transactionnel — provider abstrait.

Providers supportes:
  - `console`  : log dans la console (defaut dev/staging)
  - `smtp`     : SMTP standard (Gmail, OVH, etc.) via EMAIL_SMTP_*
  - `sendgrid` : API SendGrid via SENDGRID_API_KEY

En production, choisir `smtp` ou `sendgrid`. `console` est explicitement
deconseille en prod (warning au demarrage).
"""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from typing import Protocol

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class EmailProvider(Protocol):
    name: str

    def send(self, *, to: str, subject: str, html: str, text: str) -> bool: ...


class ConsoleEmailProvider:
    name = "console"

    def send(self, *, to: str, subject: str, html: str, text: str) -> bool:
        # ATTENTION: ne JAMAIS logger le contenu de tokens en prod.
        logger.info(
            "[email:console] to=%s subject=%s preview=%s",
            to, subject, (text or "")[:80].replace("\n", " "),
        )
        return True


class SMTPEmailProvider:
    name = "smtp"

    def send(self, *, to: str, subject: str, html: str, text: str) -> bool:
        host = settings.EMAIL_SMTP_HOST
        if not host:
            raise RuntimeError("EMAIL_SMTP_HOST missing")
        msg = EmailMessage()
        msg["From"] = settings.EMAIL_FROM
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(text)
        msg.add_alternative(html, subtype="html")

        port = settings.EMAIL_SMTP_PORT
        try:
            with smtplib.SMTP(host, port, timeout=15) as server:
                server.ehlo()
                try:
                    server.starttls()
                    server.ehlo()
                except Exception:
                    pass
                if settings.EMAIL_SMTP_USER and settings.EMAIL_SMTP_PASSWORD:
                    server.login(
                        settings.EMAIL_SMTP_USER, settings.EMAIL_SMTP_PASSWORD
                    )
                server.send_message(msg)
            return True
        except Exception as e:
            logger.error("SMTP send failed (to=%s): %s", to, e)
            return False


class SendgridEmailProvider:
    name = "sendgrid"
    _url = "https://api.sendgrid.com/v3/mail/send"

    def send(self, *, to: str, subject: str, html: str, text: str) -> bool:
        api_key = settings.SENDGRID_API_KEY
        if not api_key:
            raise RuntimeError("SENDGRID_API_KEY missing")
        payload = {
            "personalizations": [{"to": [{"email": to}]}],
            "from": {"email": _bare_email(settings.EMAIL_FROM)},
            "subject": subject,
            "content": [
                {"type": "text/plain", "value": text},
                {"type": "text/html", "value": html},
            ],
        }
        try:
            with httpx.Client(timeout=15) as client:
                resp = client.post(
                    self._url,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
            if resp.status_code >= 400:
                logger.error("SendGrid send failed (%s): %s", resp.status_code, resp.text[:200])
                return False
            return True
        except Exception as e:
            logger.error("SendGrid send error: %s", e)
            return False


def _bare_email(s: str) -> str:
    if "<" in s and ">" in s:
        return s.split("<")[1].rstrip(">").strip()
    return s.strip()


def get_email_provider() -> EmailProvider:
    name = (settings.EMAIL_PROVIDER or "console").lower()
    if name == "sendgrid":
        return SendgridEmailProvider()
    if name == "smtp":
        return SMTPEmailProvider()
    return ConsoleEmailProvider()


def send_password_reset_email(*, to_email: str, reset_url: str) -> bool:
    subject = "Reinitialise ton mot de passe AutoEdit"
    text = (
        f"Tu as demande une reinitialisation de mot de passe.\n\n"
        f"Clique sur ce lien pour creer un nouveau mot de passe "
        f"(valable 15 minutes):\n{reset_url}\n\n"
        f"Si tu n'as rien demande, ignore ce message."
    )
    html = f"""<!doctype html><html><body style="font-family:Inter,system-ui,sans-serif;background:#0a0a0f;color:#fff;padding:32px">
  <div style="max-width:520px;margin:auto;background:#16171f;border:1px solid rgba(255,255,255,.08);border-radius:16px;padding:32px">
    <h1 style="margin:0 0 16px;font-size:22px">Reinitialise ton mot de passe</h1>
    <p style="color:rgba(255,255,255,.7);line-height:1.6">Tu as demande une reinitialisation. Clique sur le bouton ci-dessous (valable 15 minutes).</p>
    <p style="margin:24px 0"><a href="{reset_url}" style="display:inline-block;padding:12px 24px;background:#2a55f5;color:#fff;text-decoration:none;border-radius:8px;font-weight:600">Choisir un nouveau mot de passe</a></p>
    <p style="color:rgba(255,255,255,.45);font-size:12px">Si tu n'as rien demande, ignore ce message. Le lien expire dans 15 minutes.</p>
  </div></body></html>"""
    try:
        return get_email_provider().send(to=to_email, subject=subject, html=html, text=text)
    except Exception as e:
        logger.error("Email send failed: %s", e)
        return False


def send_job_completed_email(*, to_email: str, video_title: str, download_url: str) -> bool:
    subject = f"Ta video « {video_title} » est prete"
    text = (
        f"Bonne nouvelle: ta video « {video_title} » est prete a telecharger.\n\n"
        f"{download_url}\n"
    )
    html = f"""<!doctype html><html><body style="font-family:Inter,system-ui,sans-serif;background:#0a0a0f;color:#fff;padding:32px">
  <div style="max-width:520px;margin:auto;background:#16171f;border:1px solid rgba(255,255,255,.08);border-radius:16px;padding:32px">
    <h1 style="margin:0 0 16px;font-size:22px">Ta video est prete</h1>
    <p style="color:rgba(255,255,255,.7)">« {video_title} » a fini d'etre montee par AutoEdit.</p>
    <p style="margin:24px 0"><a href="{download_url}" style="display:inline-block;padding:12px 24px;background:#2a55f5;color:#fff;text-decoration:none;border-radius:8px;font-weight:600">Telecharger</a></p>
  </div></body></html>"""
    try:
        return get_email_provider().send(to=to_email, subject=subject, html=html, text=text)
    except Exception as e:
        logger.error("Email send failed: %s", e)
        return False
