import hashlib
import hmac
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


def password_fingerprint(password_hash: str | None) -> str:
    """Empreinte courte du hash de mot de passe, embarquée dans les JWT.

    Changer (ou réinitialiser) le mot de passe change le hash, donc
    l'empreinte: tous les tokens émis avant deviennent invalides. C'est ce
    qui déconnecte un voleur de session après un changement de mot de passe
    et rend les liens de réinitialisation à usage unique — sans table de
    sessions ni migration.
    """
    if not password_hash:
        return ""
    return hmac.new(
        settings.SECRET_KEY.encode(), password_hash.encode(), hashlib.sha256
    ).hexdigest()[:16]


def token_matches_password(payload: dict, password_hash: str | None) -> bool:
    """True si le token a été émis pour le mot de passe ACTUEL.

    Les tokens émis avant l'ajout de l'empreinte (pas de claim `pwd`) restent
    acceptés jusqu'à leur expiration naturelle.
    """
    claim = payload.get("pwd")
    if claim is None:
        return True
    return hmac.compare_digest(str(claim), password_fingerprint(password_hash))


def create_access_token(user_id: str, password_hash: str | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {"sub": user_id, "exp": expire, "type": "access"}
    if password_hash:
        to_encode["pwd"] = password_fingerprint(password_hash)
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(user_id: str, password_hash: str | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode = {"sub": user_id, "exp": expire, "type": "refresh", "jti": str(uuid4())}
    if password_hash:
        to_encode["pwd"] = password_fingerprint(password_hash)
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_token_pair(user) -> tuple[str, str]:
    """(access, refresh) liés au mot de passe courant de *user*."""
    uid = str(user.id)
    return (
        create_access_token(uid, user.password_hash),
        create_refresh_token(uid, user.password_hash),
    )


def _create_reset_token(user_id: str, password_hash: str | None = None) -> str:
    """Create a short-lived password reset token (15 minutes).

    Lié au hash du mot de passe courant: une fois le mot de passe changé, le
    même lien ne peut plus resservir (usage unique).
    """
    expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode = {"sub": user_id, "exp": expire, "type": "reset", "jti": str(uuid4())}
    if password_hash:
        to_encode["pwd"] = password_fingerprint(password_hash)
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
