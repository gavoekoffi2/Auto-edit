"""Tests d'intégration HTTP des parcours critiques avant lancement.

L'application FastAPI réelle tourne contre une base SQLite en mémoire (les
modèles utilisent des types portables), avec Redis et Celery remplacés par
des doubles en mémoire. Ces tests verrouillent les corrections suivantes:

* sessions révoquées après changement / réinitialisation du mot de passe,
  lien de réinitialisation à usage unique ;
* limitation des connexions sur les ÉCHECS uniquement ;
* job commité AVANT sa mise en file (plus de job « pending » éternel) ;
* quota mensuel gratuit appliqué aux montages (plus de contournement) ;
* paiement: abonnement à durée limitée, vérification au retour, webhook signé ;
* rôles admin: pas d'escalade de privilèges.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta, timezone

import pytest

pytest.importorskip("aiosqlite")
pytest.importorskip("httpx")
pytest.importorskip("passlib.context")

import httpx  # noqa: E402
from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

try:
    from passlib.context import CryptContext  # noqa: F401
    from jose import jwt  # noqa: F401
    from app.main import app
    from app.db.base import Base
    from app.db.session import get_db
    from app.models.job import Job
    from app.models.payment import Payment
    from app.models.user import User
    from app.models.video import Video
except Exception as exc:  # pragma: no cover - dépendances absentes
    pytest.skip(f"app stack unavailable: {exc}", allow_module_level=True)


from sqlalchemy.dialects.postgresql import UUID as PG_UUID  # noqa: E402
from sqlalchemy.ext.compiler import compiles  # noqa: E402


@compiles(PG_UUID, "sqlite")
def _uuid_on_sqlite(type_, compiler, **kw):  # pragma: no cover - DDL only
    # Les modèles déclarent le type UUID de PostgreSQL; SQLite le stocke en texte.
    return "CHAR(32)"


# --------------------------------------------------------------------------
# Doubles Redis / Celery
# --------------------------------------------------------------------------
class FakeRedis:
    def __init__(self):
        self.store: dict[str, int | str] = {}

    async def get(self, key):
        v = self.store.get(key)
        return None if v is None else str(v).encode()

    async def ttl(self, key):
        return 60

    async def delete(self, key):
        self.store.pop(key, None)

    async def setex(self, key, ttl, value):
        self.store[key] = value

    async def ping(self):
        return True

    def pipeline(self):
        redis = self

        class _Pipe:
            def __init__(self):
                self.ops = []

            def incr(self, key):
                self.ops.append(key)

            def expire(self, key, ttl):
                pass

            async def execute(self):
                for key in self.ops:
                    redis.store[key] = int(redis.store.get(key, 0)) + 1

        return _Pipe()


@pytest.fixture
def env(monkeypatch, tmp_path):
    db_file = tmp_path / "test.db"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_file}",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _init():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_init())

    async def override_get_db():
        async with Session() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db

    fake_redis = FakeRedis()

    async def _get_redis():
        return fake_redis

    from app.services import rate_limiter
    monkeypatch.setattr(rate_limiter, "_get_redis", _get_redis)

    from app.config import settings
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "ADMIN_EMAILS", "")

    dispatched: list[dict] = []

    from app.workers import tasks

    def fake_apply_async(args=None, task_id=None, **_):
        # Le job DOIT déjà être commité quand il part au worker: on le relit
        # depuis une connexion indépendante (comme le ferait le worker).
        import sqlite3
        conn = sqlite3.connect(str(db_file))
        try:
            row = conn.execute("SELECT 1 FROM jobs WHERE id = ?", (_uuid(args[0]).hex,)).fetchone()
        finally:
            conn.close()
        dispatched.append({"job_id": args[0], "task_id": task_id, "visible": row is not None})

    monkeypatch.setattr(tasks.process_video_task, "apply_async", fake_apply_async)
    monkeypatch.setattr(tasks.process_clips_task, "apply_async", fake_apply_async)

    yield {"Session": Session, "dispatched": dispatched, "tmp": tmp_path, "redis": fake_redis}

    app.dependency_overrides.clear()
    asyncio.run(engine.dispose())


def _uuid(value):
    import uuid
    return uuid.UUID(str(value))


def run(coro):
    return asyncio.run(coro)


async def _client():
    return httpx.AsyncClient(app=app, base_url="http://test")


async def _signup(c, email="user@example.com", password="Secret123"):
    r = await c.post("/api/v1/auth/signup", json={"email": email, "password": password})
    assert r.status_code == 201, r.text
    return r.json()


def _auth(tok):
    return {"Authorization": f"Bearer {tok}"}


# --------------------------------------------------------------------------
# Auth
# --------------------------------------------------------------------------
def test_password_change_revokes_other_sessions(env):
    async def scenario():
        async with await _client() as c:
            old = await _signup(c)
            assert (await c.get("/api/v1/auth/me", headers=_auth(old["access_token"]))).status_code == 200

            r = await c.post(
                "/api/v1/auth/password-change",
                json={"current_password": "Secret123", "new_password": "NewSecret456"},
                headers=_auth(old["access_token"]),
            )
            assert r.status_code == 200, r.text
            new = r.json()

            # Anciennes sessions (autre appareil / token volé) révoquées.
            assert (await c.get("/api/v1/auth/me", headers=_auth(old["access_token"]))).status_code == 401
            r = await c.post("/api/v1/auth/refresh", json={"refresh_token": old["refresh_token"]})
            assert r.status_code == 401
            # La nouvelle session fonctionne.
            assert (await c.get("/api/v1/auth/me", headers=_auth(new["access_token"]))).status_code == 200
            r = await c.post("/api/v1/auth/refresh", json={"refresh_token": new["refresh_token"]})
            assert r.status_code == 200

    run(scenario())


def test_password_reset_link_is_single_use(env, monkeypatch):
    sent = {}

    def fake_send(*, to_email, reset_url):
        sent["url"] = reset_url
        return True

    import app.services.email as email_mod
    monkeypatch.setattr(email_mod, "send_password_reset_email", fake_send)

    async def scenario():
        async with await _client() as c:
            session = await _signup(c)
            r = await c.post("/api/v1/auth/password-reset/request", json={"email": "user@example.com"})
            assert r.status_code == 200
            token = sent["url"].split("token=", 1)[1]
            assert "/reset-password?token=" in sent["url"]

            r = await c.post("/api/v1/auth/password-reset/confirm",
                             json={"token": token, "new_password": "Brand1New"})
            assert r.status_code == 200, r.text
            # Réutiliser le même lien est refusé.
            r = await c.post("/api/v1/auth/password-reset/confirm",
                             json={"token": token, "new_password": "Other2Pass"})
            assert r.status_code == 400
            # L'ancienne session est révoquée, le nouveau mot de passe marche.
            assert (await c.get("/api/v1/auth/me", headers=_auth(session["access_token"]))).status_code == 401
            r = await c.post("/api/v1/auth/login", json={"email": "user@example.com", "password": "Brand1New"})
            assert r.status_code == 200

    run(scenario())


def test_login_limit_counts_failures_only(env):
    async def scenario():
        async with await _client() as c:
            await _signup(c)
            # Beaucoup de connexions RÉUSSIES depuis la même IP: jamais bloquées.
            for _ in range(8):
                r = await c.post("/api/v1/auth/login",
                                 json={"email": "user@example.com", "password": "Secret123"})
                assert r.status_code == 200
            # 5 échecs -> le 6e essai (même correct) est limité.
            for _ in range(5):
                r = await c.post("/api/v1/auth/login",
                                 json={"email": "user@example.com", "password": "wrong999"})
                assert r.status_code == 401
                assert r.json()["detail"] == "Email ou mot de passe incorrect."
            r = await c.post("/api/v1/auth/login",
                             json={"email": "user@example.com", "password": "Secret123"})
            assert r.status_code == 429

    run(scenario())


def test_duplicate_signup_returns_409(env):
    async def scenario():
        async with await _client() as c:
            await _signup(c)
            r = await c.post("/api/v1/auth/signup",
                             json={"email": "USER@example.com", "password": "Secret123"})
            assert r.status_code == 409

    run(scenario())


# --------------------------------------------------------------------------
# Jobs
# --------------------------------------------------------------------------
async def _make_video(env, user_id):
    rel = f"{user_id}/src.mp4"
    path = env["tmp"] / str(user_id)
    path.mkdir(parents=True, exist_ok=True)
    (path / "src.mp4").write_bytes(b"\x00" * 64)
    async with env["Session"]() as s:
        v = Video(user_id=user_id, title="src.mp4", original_path=rel, size_bytes=64, duration_s=30.0)
        s.add(v)
        await s.commit()
        return v.id


async def _user_id(env, email="user@example.com"):
    async with env["Session"]() as s:
        return (await s.execute(select(User.id).where(User.email == email))).scalar_one()


async def _set_job_status(env, job_id, status):
    async with env["Session"]() as s:
        job = (await s.execute(select(Job).where(Job.id == _uuid(job_id)))).scalar_one()
        job.status = status
        await s.commit()


def test_job_is_committed_before_dispatch_and_free_monthly_quota(env):
    async def scenario():
        async with await _client() as c:
            tok = (await _signup(c))["access_token"]
            uid = await _user_id(env)
            vid = await _make_video(env, uid)

            ids = []
            for _ in range(2):
                r = await c.post("/api/v1/jobs", json={"video_id": str(vid)}, headers=_auth(tok))
                assert r.status_code == 201, r.text
                ids.append(r.json()["id"])
                await _set_job_status(env, ids[-1], "completed")

            # Chaque job était visible en base au moment de sa mise en file.
            assert [d["visible"] for d in env["dispatched"]] == [True, True]
            assert [d["task_id"] for d in env["dispatched"]] == ids

            # 3e montage du mois sur la MÊME vidéo: refusé (plan gratuit = 2).
            r = await c.post("/api/v1/jobs", json={"video_id": str(vid)}, headers=_auth(tok))
            assert r.status_code == 429
            assert "montages gratuits" in r.json()["detail"]

            # Un montage échoué ne consomme pas le quota.
            await _set_job_status(env, ids[0], "failed")
            r = await c.post("/api/v1/jobs", json={"video_id": str(vid)}, headers=_auth(tok))
            assert r.status_code == 201
            await _set_job_status(env, r.json()["id"], "completed")

            # Contournement historique: supprimer la vidéo (et donc ses jobs en
            # cascade) ne doit PAS rendre de montages gratuits.
            r = await c.delete(f"/api/v1/videos/{vid}", headers=_auth(tok))
            assert r.status_code == 204
            vid2 = await _make_video(env, uid)
            r = await c.post("/api/v1/jobs", json={"video_id": str(vid2)}, headers=_auth(tok))
            assert r.status_code == 429

    run(scenario())


def test_deleting_video_cancels_its_running_jobs(env, monkeypatch):
    from app.workers import celery_app as celery_mod
    revoked = []
    monkeypatch.setattr(celery_mod.celery_app.control, "revoke",
                        lambda task_id, **kw: revoked.append(task_id))

    async def scenario():
        async with await _client() as c:
            tok = (await _signup(c))["access_token"]
            uid = await _user_id(env)
            vid = await _make_video(env, uid)
            r = await c.post("/api/v1/jobs", json={"video_id": str(vid)}, headers=_auth(tok))
            job_id = r.json()["id"]
            await _set_job_status(env, job_id, "processing")

            r = await c.delete(f"/api/v1/videos/{vid}", headers=_auth(tok))
            assert r.status_code == 204
            assert revoked == [job_id]

    run(scenario())


# --------------------------------------------------------------------------
# Paiement
# --------------------------------------------------------------------------
def test_checkout_verify_activates_time_limited_subscription(env, monkeypatch):
    from app.api.v1 import payments as pay_api

    captured = {}

    async def fake_checkout(*, plan, currency, user_email, callback_url, full_name):
        captured["callback_url"] = callback_url
        return {"tx_id": "tx-1", "checkout_url": "https://sandbox-process.fedapay.com/tok", "amount": 5000}

    async def fake_fetch(tx_id):
        return {"status": "approved", "amount": 5000}

    monkeypatch.setattr(pay_api, "create_checkout", fake_checkout)
    monkeypatch.setattr(pay_api, "fetch_transaction", fake_fetch)

    async def scenario():
        async with await _client() as c:
            tok = (await _signup(c))["access_token"]
            r = await c.post("/api/v1/payments/checkout", json={"plan": "pro"}, headers=_auth(tok))
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["checkout_url"].startswith("https://")
            assert captured["callback_url"].endswith(f"/billing/return?payment_id={body['payment_id']}")

            r = await c.post(f"/api/v1/payments/{body['payment_id']}/verify", headers=_auth(tok))
            assert r.status_code == 200, r.text
            data = r.json()
            assert data["status"] == "completed"
            assert data["effective_plan"] == "pro"
            expires = datetime.fromisoformat(data["subscription_expires_at"])
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            delta = expires - datetime.now(timezone.utc)
            assert timedelta(days=29) < delta <= timedelta(days=30, minutes=1)

            # Idempotent: une 2e vérification ne prolonge pas l'abonnement.
            r = await c.post(f"/api/v1/payments/{body['payment_id']}/verify", headers=_auth(tok))
            assert r.json()["subscription_expires_at"] == data["subscription_expires_at"]

    run(scenario())


def _signed(body: bytes, secret: str, ts: int | None = None) -> str:
    ts = int(time.time()) if ts is None else ts
    sig = hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    return f"t={ts},s={sig}"


def test_webhook_requires_valid_fresh_signature(env, monkeypatch):
    from app.api.v1 import payments as pay_api
    from app.config import settings

    monkeypatch.setattr(settings, "FEDAPAY_WEBHOOK_SECRET", "wh_sandbox_secret")
    monkeypatch.setattr(settings, "FEDAPAY_SECRET_KEY", "sk_sandbox_x")

    async def fake_fetch(tx_id):
        return {"status": "approved", "amount": 15000}

    monkeypatch.setattr(pay_api, "fetch_transaction", fake_fetch)

    async def scenario():
        async with await _client() as c:
            await _signup(c)
            uid = await _user_id(env)
            async with env["Session"]() as s:
                s.add(Payment(user_id=uid, fedapay_tx_id="42", amount=15000, currency="XOF", plan="enterprise"))
                await s.commit()

            body = json.dumps({"name": "transaction.approved",
                               "entity": {"id": 42, "status": "approved"}}).encode()
            bad = await c.post("/api/v1/payments/webhook", content=body,
                               headers={"X-FEDAPAY-SIGNATURE": _signed(body, "wrong")})
            assert bad.status_code == 403
            stale = await c.post("/api/v1/payments/webhook", content=body,
                                 headers={"X-FEDAPAY-SIGNATURE": _signed(body, "wh_sandbox_secret", ts=int(time.time()) - 3600)})
            assert stale.status_code == 403

            ok = await c.post("/api/v1/payments/webhook", content=body,
                              headers={"X-FEDAPAY-SIGNATURE": _signed(body, "wh_sandbox_secret")})
            assert ok.status_code == 200 and ok.json()["status"] == "processed"
            again = await c.post("/api/v1/payments/webhook", content=body,
                                 headers={"X-FEDAPAY-SIGNATURE": _signed(body, "wh_sandbox_secret")})
            assert again.json()["status"] == "already_processed"

            async with env["Session"]() as s:
                user = (await s.execute(select(User).where(User.id == uid))).scalar_one()
                assert user.plan == "enterprise"
                assert user.subscription_expires_at is not None

    run(scenario())


def test_webhook_amount_mismatch_does_not_activate(env, monkeypatch):
    from app.api.v1 import payments as pay_api
    from app.config import settings

    monkeypatch.setattr(settings, "FEDAPAY_WEBHOOK_SECRET", "whsec")
    monkeypatch.setattr(settings, "FEDAPAY_SECRET_KEY", "sk")

    async def fake_fetch(tx_id):
        return {"status": "approved", "amount": 100}

    monkeypatch.setattr(pay_api, "fetch_transaction", fake_fetch)

    async def scenario():
        async with await _client() as c:
            await _signup(c)
            uid = await _user_id(env)
            async with env["Session"]() as s:
                s.add(Payment(user_id=uid, fedapay_tx_id="7", amount=5000, currency="XOF", plan="pro"))
                await s.commit()
            body = json.dumps({"entity": {"id": 7}}).encode()
            r = await c.post("/api/v1/payments/webhook", content=body,
                             headers={"X-FEDAPAY-SIGNATURE": _signed(body, "whsec")})
            assert r.status_code == 200
            async with env["Session"]() as s:
                user = (await s.execute(select(User).where(User.id == uid))).scalar_one()
                assert user.plan == "free"

    run(scenario())


# --------------------------------------------------------------------------
# Admin
# --------------------------------------------------------------------------
def test_plain_admin_cannot_escalate_or_delete(env):
    async def scenario():
        async with await _client() as c:
            admin_tok = (await _signup(c, "admin@example.com"))["access_token"]
            await _signup(c, "victim@example.com")
            async with env["Session"]() as s:
                admin = (await s.execute(select(User).where(User.email == "admin@example.com"))).scalar_one()
                admin.is_admin = True
                await s.commit()
            victim_id = await _user_id(env, "victim@example.com")

            r = await c.post("/api/v1/admin/subscriptions/grant", headers=_auth(admin_tok),
                             json={"email": "victim@example.com", "plan": "pro", "is_admin": True})
            assert r.status_code == 403
            # Même formulaire sans changement de rôle: autorisé.
            r = await c.post("/api/v1/admin/subscriptions/grant", headers=_auth(admin_tok),
                             json={"email": "victim@example.com", "plan": "pro", "is_admin": False,
                                   "duration_days": 30})
            assert r.status_code == 200, r.text
            r = await c.delete(f"/api/v1/admin/users/{victim_id}", headers=_auth(admin_tok))
            assert r.status_code == 403

    run(scenario())
