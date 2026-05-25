"""Tests du service email — provider abstrait."""
from app.services.email import (
    ConsoleEmailProvider,
    SendgridEmailProvider,
    SMTPEmailProvider,
    get_email_provider,
    _bare_email,
)


def test_console_provider_returns_true_without_io():
    p = ConsoleEmailProvider()
    assert p.send(to="a@b.c", subject="x", html="<p>x</p>", text="x") is True


def test_bare_email_strips_display_name():
    assert _bare_email("AutoEdit <noreply@autoedit.app>") == "noreply@autoedit.app"
    assert _bare_email("noreply@autoedit.app") == "noreply@autoedit.app"


def test_get_email_provider_console_by_default(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "EMAIL_PROVIDER", "console", raising=False)
    assert isinstance(get_email_provider(), ConsoleEmailProvider)


def test_get_email_provider_smtp_when_configured(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "EMAIL_PROVIDER", "smtp", raising=False)
    assert isinstance(get_email_provider(), SMTPEmailProvider)


def test_get_email_provider_sendgrid_when_configured(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "EMAIL_PROVIDER", "sendgrid", raising=False)
    assert isinstance(get_email_provider(), SendgridEmailProvider)
