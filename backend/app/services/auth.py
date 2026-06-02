import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {"sub": user_id, "exp": expire, "type": "access"}
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode = {"sub": user_id, "exp": expire, "type": "refresh", "jti": str(uuid4())}
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def _create_reset_token(user_id: str) -> str:
    """Create a short-lived password reset token (15 minutes)."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode = {"sub": user_id, "exp": expire, "type": "reset", "jti": str(uuid4())}
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None


async def revoke_token(jti: str, ttl_seconds: int) -> None:
    """Add a token jti to the Redis blacklist for `ttl_seconds`.

    Le worker FastAPI verifiera la blacklist a chaque requete authentifiee.
    Sans Redis, cette fonction echoue silencieusement (l'access token
    expire toujours apres ACCESS_TOKEN_EXPIRE_MINUTES de toute facon).
    """
    if not jti or ttl_seconds <= 0:
        return
    try:
        from app.services.rate_limiter import _get_redis
        r = await _get_redis()
        await r.setex(f"revoked_jti:{jti}", ttl_seconds, "1")
    except Exception as e:
        logger.warning("Could not revoke token jti=%s: %s", jti, e)


async def is_token_revoked(jti: str) -> bool:
    if not jti:
        return False
    try:
        from app.services.rate_limiter import _get_redis
        r = await _get_redis()
        val = await r.get(f"revoked_jti:{jti}")
        return val is not None
    except Exception:
        # Si Redis tombe, on autorise — l'access token a une duree de vie courte
        return False
