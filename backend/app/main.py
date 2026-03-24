import uuid
import logging
from datetime import datetime, timezone

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.v1.router import api_router
from app.config import settings

logger = logging.getLogger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Add unique request ID to each request for tracing."""

    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


app = FastAPI(
    title="AutoEdit API",
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
        import redis as redis_lib

        r = redis_lib.from_url(settings.REDIS_URL)
        r.ping()
        health["redis"] = "connected"
        r.close()
    except Exception as e:
        health["redis"] = f"error: {str(e)}"
        health["status"] = "degraded"

    return health
