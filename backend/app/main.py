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


app = FastAPI(
    title="CutForge API",
    description="AI-powered automatic video editing SaaS platform",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# Request ID middleware
app.add_middleware(RequestIDMiddleware)

# CORS - use configured origins, not wildcard
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/api/health")
async def health_check():
    """Health check with dependency verification."""
    health = {
        "status": "healthy",
        "service": "autoedit",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # Check database
    try:
        from app.db.session import async_engine
        from sqlalchemy import text

        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        health["database"] = "connected"
    except Exception as e:
        health["database"] = f"error: {str(e)}"
        health["status"] = "degraded"

    # Check Redis
    try:
        from app.services.rate_limiter import _get_redis
        r = await _get_redis()
        await r.ping()
        health["redis"] = "connected"
    except Exception as e:
        health["redis"] = f"error: {str(e)}"
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
        health["disk"] = f"error: {str(e)}"

    return health
