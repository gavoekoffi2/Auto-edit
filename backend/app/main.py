import uuid
import logging
from datetime import datetime, timezone

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.v1.router import api_router
from app.config import settings

logger = logging.getLogger(__name__)

# Initialise Sentry des le bootstrap si configure (et pas en dev local).
if settings.SENTRY_DSN:
    try:
        import sentry_sdk
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.APP_ENV,
            traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
            send_default_pii=False,
        )
        logger.info("Sentry initialized (env=%s)", settings.APP_ENV)
    except Exception as e:
        logger.warning("Sentry init failed: %s", e)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Add unique request ID to each request for tracing."""

    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Standard hardening headers on every API response.

    Le proxy (Caddy/nginx) peut aussi les poser, mais l'API doit rester sûre
    même exposée directement (dev, docker-compose sans proxy).
    """

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy", "camera=(), microphone=(), geolocation=()"
        )
        if settings.is_production:
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return response


app = FastAPI(
    title="CutForge API",
    description="AI-powered automatic video editing SaaS platform",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# Request ID + security headers middlewares
app.add_middleware(RequestIDMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

# CORS - use configured origins, not wildcard
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/api/health/live")
async def liveness():
    """Liveness: le process répond. Aucune dépendance vérifiée."""
    return {"status": "alive"}


@app.get("/api/health/ready")
async def readiness():
    """Readiness: dépendances critiques prêtes (DB + Redis). 503 sinon."""
    from fastapi.responses import JSONResponse
    ready = True
    checks = {}
    try:
        from app.db.session import async_engine
        from sqlalchemy import text
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        logger.error("readiness: database error: %s", e)
        checks["database"] = "error"
        ready = False
    try:
        from app.services.rate_limiter import _get_redis
        r = await _get_redis()
        await r.ping()
        checks["redis"] = "ok"
    except Exception as e:
        logger.error("readiness: redis error: %s", e)
        checks["redis"] = "error"
        ready = False
    body = {"status": "ready" if ready else "not_ready", **checks}
    return JSONResponse(status_code=200 if ready else 503, content=body)


@app.get("/api/health")
async def health_check():
    """Health check with dependency verification."""
    health = {
        "status": "healthy",
        "service": "autoedit",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # Check database. Le détail de l'erreur part dans les logs, PAS dans la
    # réponse: l'endpoint est public et un message d'exception peut divulguer
    # hôtes internes / DSN / versions.
    try:
        from app.db.session import async_engine
        from sqlalchemy import text

        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        health["database"] = "connected"
    except Exception as e:
        logger.error("health check: database error: %s", e)
        health["database"] = "error"
        health["status"] = "degraded"

    # Check Redis
    try:
        from app.services.rate_limiter import _get_redis
        r = await _get_redis()
        await r.ping()
        health["redis"] = "connected"
    except Exception as e:
        logger.error("health check: redis error: %s", e)
        health["redis"] = "error"
        health["status"] = "degraded"

    # Espace disque du volume d'uploads — un disque plein casse upload ET rendu.
    try:
        import shutil
        usage = shutil.disk_usage(settings.UPLOAD_DIR)
        free_gb = usage.free / 1e9
        health["disk_free_gb"] = round(free_gb, 1)
        health["disk_used_pct"] = round(usage.used / usage.total * 100, 1)
        if free_gb < 2:
            health["status"] = "degraded"
            health["disk_warning"] = "espace disque critique"
    except Exception as e:
        logger.error("health check: disk error: %s", e)
        health["disk"] = "error"

    return health
