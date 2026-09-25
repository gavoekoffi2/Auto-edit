"""Parcours utilisateur de bout en bout sur la VRAIE application FastAPI.

Base SQLite en mémoire (aiosqlite), Redis simulé en mémoire, Celery et
FedaPay neutralisés. Couvre les régressions corrigées avant lancement:
reset de mot de passe à usage unique, invalidation des sessions, blocage de
login sur les seuls échecs, quota Free non contournable par suppression,
paiement = abonnement LIMITÉ dans le temps, erreurs de job sans détail interne.
"""
import asyncio
import io
import re
import uuid
from datetime import datetime, timezone

import pytest

pytest.importorskip("aiosqlite")
pytest.importorskip("psycopg2")
pytest.importorskip("jose.jwt")
pytest.importorskip("passlib.context")
pytest.importorskip("fastapi.testclient")


class FakeRedis:
    def __init__(self):
        self.store: dict[str, int | str] = {}

    async def get(self, k):
        v = self.store.get(k)
        return None if v is None else str(v).encode()

    async def ttl(self, k):
        return 600

    async def setex(self, k, ttl, v):
        self.store[k] = v

    async def delete(self, k):
        self.store.pop(k, None)

    async def ping(self):
        return True

    def pipeline(self):
        outer = self

        class P:
            def __init__(self):
                self.ops = []

            def incr(self, k):
                self.ops.append(k)

            def expire(self, *_):
                pass

            async def execute(self):
                for k in self.ops:
                    outer.store[k] = int(outer.store.get(k, 0)) + 1

        return P()


def _sqlite_uuid_support():
    """Les modèles utilisent le type UUID PostgreSQL: rendu CHAR(32) sous SQLite."""
    from sqlalchemy.dialects.postgresql import UUID as PG_UUID
    from sqlalchemy.ext.compiler import compiles

    @compiles(PG_UUID, "sqlite")
    def _uuid_sqlite(_type, _compiler, **_kw):  # pragma: no cover - glue
        return "CHAR(32)"


@pytest.fixture()
def env(monkeypatch, tmp_path):
    _sqlite_uuid_support()
    from fastapi.testclient import TestClient
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy.pool import StaticPool

    from app.config import settings
    from app.db.base import Base
    from app.db.session import get_db
    from app.main import app as fastapi_app
    from app.models import user as _u, video as _v, job as _j, payment as _p  # noqa: F401
    from app.services import rate_limiter
    from app.api.v1 import videos as videos_api
    from app.workers import tasks

    engine = create_async_engine(
        "sqlite+aiosqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    async def init():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    asyncio.run(init())
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _get_db():
        async with Session() as s:
            try:
                yield s
                await s.commit()
            except Exception:
                await s.rollback()
                raise

    fastapi_app.dependency_overrides[get_db] = _get_db
    redis = FakeRedis()

    async def fake_redis():
        return redis
    monkeypatch.setattr(rate_limiter, "_get_redis", fake_redis)
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "UPLOAD_MIN_FREE_GB", 0.0)
    monkeypatch.setattr(settings, "FEDAPAY_SECRET_KEY", "sk_sandbox_test")
    monkeypatch.setattr(settings, "FEDAPAY_WEBHOOK_SECRET", None)
    monkeypatch.setattr(videos_api, "get_video_duration", lambda _p: 60.0)
    dispatched = []
    monkeypatch.setattr(tasks.process_video_task, "apply_async",
                        lambda *a, **k: dispatched.append(k.get("task_id")), raising=False)
    emails = []
    import app.services.email as email_mod
    monkeypatch.setattr(email_mod, "send_password_reset_email",
                        lambda **kw: emails.append(kw) or True)

    client = TestClient(fastapi_app)
    yield {"client": client, "emails": emails, "Session": Session, "redis": redis,
           "dispatched": dispatched}
    fastapi_app.dependency_overrides.clear()


MP4_HEAD = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64


def _signup(c, email="awa@example.com", pw="motdepasse1"):
    r = c.post("/api/v1/auth/signup", json={"email": email, "password": pw})
    assert r.status_code == 201, r.text
    return r.json()


def _auth(tokens):
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def test_password_reset_flow_single_use_and_revokes_sessions(env):
    c = env["client"]
    old = _signup(c)
    assert c.get("/api/v1/auth/me", headers=_auth(old)).status_code == 200

    r = c.post("/api/v1/auth/password-reset/request", json={"email": "AWA@example.com "})
    assert r.status_code == 200
    url = env["emails"][-1]["reset_url"]
    assert "/reset-password?token=" in url
    token = url.split("token=")[1]

    r = c.post("/api/v1/auth/password-reset/confirm",
               json={"token": token, "new_password": "nouveau123"})
    assert r.status_code == 200, r.text
    # Le lien ne sert qu'une fois.
    r = c.post("/api/v1/auth/password-reset/confirm",
               json={"token": token, "new_password": "encoreun123"})
    assert r.status_code == 400
    # Les anciennes sessions sont invalidées, access ET refresh.
    assert c.get("/api/v1/auth/me", headers=_auth(old)).status_code == 401
    assert c.post("/api/v1/auth/refresh",
                  json={"refresh_token": old["refresh_token"]}).status_code == 401
    # Nouveau mot de passe OK, ancien refusé.
    assert c.post("/api/v1/auth/login",
                  json={"email": "awa@example.com", "password": "motdepasse1"}).status_code == 401
    assert c.post("/api/v1/auth/login",
                  json={"email": "awa@example.com", "password": "nouveau123"}).status_code == 200


def test_successful_logins_never_lock_out_shared_ip(env):
    c = env["client"]
    _signup(c)
    for _ in range(20):  # >> ancien seuil de 5 tentatives (succès compris)
        r = c.post("/api/v1/auth/login",
                   json={"email": "awa@example.com", "password": "motdepasse1"})
        assert r.status_code == 200
    # Les échecs, eux, finissent par bloquer ce compte.
    codes = [c.post("/api/v1/auth/login",
                    json={"email": "awa@example.com", "password": "mauvais123"}).status_code
             for _ in range(10)]
    assert codes[0] == 401 and codes[-1] == 429


def test_logout_revokes_refresh_token(env):
    c = env["client"]
    t = _signup(c)
    assert c.post("/api/v1/auth/logout", json={"refresh_token": t["refresh_token"]}).status_code == 200
    assert c.post("/api/v1/auth/refresh",
                  json={"refresh_token": t["refresh_token"]}).status_code == 401


def _upload(c, tokens, name="clip.mp4"):
    return c.post("/api/v1/videos/upload", headers=_auth(tokens),
                  files={"file": (name, io.BytesIO(MP4_HEAD), "video/mp4")})


def test_free_quota_cannot_be_reset_by_deleting_videos(env):
    c = env["client"]
    t = _signup(c)
    ids = []
    for _ in range(2):
        r = _upload(c, t)
        assert r.status_code == 201, r.text
        ids.append(r.json()["id"])
    for vid in ids:
        assert c.delete(f"/api/v1/videos/{vid}", headers=_auth(t)).status_code == 204
    assert c.get("/api/v1/videos", headers=_auth(t)).json()["total"] == 0

    check = c.get("/api/v1/videos/upload-check", headers=_auth(t)).json()
    assert check["can_upload"] is False and check["monthly_used"] == 2
    r = _upload(c, t)
    assert r.status_code == 429
    assert "Passe Pro" in r.json()["detail"]


def test_upload_rejects_unreadable_video(env, monkeypatch):
    from app.api.v1 import videos as videos_api
    monkeypatch.setattr(videos_api, "get_video_duration", lambda _p: None)
    c = env["client"]
    t = _signup(c)
    r = _upload(c, t)
    assert r.status_code == 400 and "corrompu" in r.json()["detail"]


def test_job_error_details_are_not_leaked(env):
    c = env["client"]
    t = _signup(c)
    vid = _upload(c, t).json()["id"]
    r = c.post("/api/v1/jobs", headers=_auth(t), json={"video_id": vid})
    assert r.status_code == 201, r.text
    job_id = r.json()["id"]
    assert env["dispatched"] == [job_id]

    async def fail():
        from app.models.job import Job
        async with env["Session"]() as s:
            job = await s.get(Job, uuid.UUID(job_id))
            job.status = "failed"
            job.error_message = "[RENDER_FAILED] boom (ffmpeg -i /app/uploads/secret/path.mp4)"
            await s.commit()
    asyncio.run(fail())
    body = c.get(f"/api/v1/jobs/{job_id}", headers=_auth(t)).json()
    assert body["error_code"] == "RENDER_FAILED"
    assert "/app/uploads" not in body["error_message"]


def test_payment_grants_time_limited_plan_via_verify(env, monkeypatch):
    from app.services import payment as pay

    c = env["client"]
    t = _signup(c)

    async def fake_create_checkout(**kw):
        assert "/dashboard?payment=" in kw["callback_url"]
        return {"tx_id": "777", "checkout_url": "https://process.fedapay.com/tok", "amount": 5000}

    async def fake_fetch(tx_id):
        return {"id": tx_id, "status": "approved", "amount": 5000, "currency": {"iso": "XOF"}}

    import app.api.v1.payments as payments_api
    monkeypatch.setattr(payments_api, "create_checkout", fake_create_checkout)
    monkeypatch.setattr(payments_api, "fetch_transaction", fake_fetch)

    r = c.post("/api/v1/payments/checkout", headers=_auth(t), json={"plan": "pro"})
    assert r.status_code == 200, r.text
    assert r.json()["checkout_url"].startswith("https://")
    pid = r.json()["payment_id"]

    r = c.post(f"/api/v1/payments/{pid}/verify", headers=_auth(t))
    assert r.status_code == 200 and r.json()["status"] == "completed"
    me = c.get("/api/v1/auth/me", headers=_auth(t)).json()
    assert me["effective_plan"] == "pro"
    assert me["subscription_expires_at"] is not None
    expires = datetime.fromisoformat(me["subscription_expires_at"].replace("Z", "+00:00"))
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    assert 29 <= (expires - datetime.now(timezone.utc)).days <= 30

    # Le webhook arrivé ensuite ne prolonge pas une 2e fois.
    r = c.post("/api/v1/payments/webhook", json={"entity": {"id": 777, "status": "approved"}})
    assert r.json()["status"] == "already_processed"


def test_webhook_body_status_is_never_trusted(env, monkeypatch):
    """Un faux webhook « approved » ne doit rien activer: le statut réel est relu chez FedaPay."""
    import app.api.v1.payments as payments_api
    c = env["client"]
    t = _signup(c)

    async def fake_create_checkout(**kw):
        return {"tx_id": "888", "checkout_url": "https://x/y", "amount": 5000}

    async def fake_fetch(tx_id):
        return {"id": tx_id, "status": "pending", "amount": 5000}

    monkeypatch.setattr(payments_api, "create_checkout", fake_create_checkout)
    monkeypatch.setattr(payments_api, "fetch_transaction", fake_fetch)
    c.post("/api/v1/payments/checkout", headers=_auth(t), json={"plan": "enterprise"})
    r = c.post("/api/v1/payments/webhook", json={"entity": {"id": 888, "status": "approved"}})
    assert r.json()["status"] == "pending"
    assert c.get("/api/v1/auth/me", headers=_auth(t)).json()["effective_plan"] == "free"


def test_plans_endpoint_matches_enforced_limits(env):
    from app.config import settings
    data = env["client"].get("/api/v1/payments/plans").json()
    free = next(p for p in data["plans"] if p["id"] == "free")
    assert any(f"{settings.MAX_VIDEO_DURATION_FREE // 60} min" in f for f in free["features"])
    assert not any("4K" in f for p in data["plans"] for f in p["features"])
