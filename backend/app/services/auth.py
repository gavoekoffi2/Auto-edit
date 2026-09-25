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


# Hash bcrypt factice: vérifié quand l'email est inconnu pour que la durée de
# réponse du login ne révèle pas quels emails ont un compte.
_DUMMY_HASH = "$2b$12$C6UzMDM.H6dfI/f/IKcEeO5M8C1CwQeGQ8lV1cJXb6Y4pQZ6sN4bW"


def verify_password_constant_time(plain_password: str, hashed_password: str | None) -> bool:
    if not hashed_password:
        try:
            pwd_context.verify(plain_password, _DUMMY_HASH)
        except Exception:
            pass
        return False
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False


def password_fingerprint(password_hash: str | None) -> str:
    """Empreinte courte du hash de mot de passe, embarquée dans les JWT.

    Changer/réinitialiser le mot de passe change l'empreinte: tous les jetons
    émis avant (sessions ouvertes ailleurs, lien de réinitialisation déjà
    utilisé) deviennent invalides. Le hash lui-même n'est jamais exposé.
    """
    import hashlib
    return hashlib.sha256(f"{settings.SECRET_KEY}:{password_hash or ''}".encode()).hexdigest()[:16]


def token_matches_password(payload: dict, password_hash: str | None) -> bool:
    """Vrai si le jeton a été émis pour le mot de passe actuel.

    Les jetons sans empreinte (émis avant cette mesure) restent acceptés
    jusqu'à leur expiration naturelle — pas de déconnexion massive au déploiement.
    """
    pwh = payload.get("pwh")
    if pwh is None:
        return True
    import hmac as _hmac
    return _hmac.compare_digest(str(pwh), password_fingerprint(password_hash))


def create_access_token(user_id: str, password_hash: str | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {"sub": user_id, "exp": expire, "type": "access"}
    if password_hash is not None:
        to_encode["pwh"] = password_fingerprint(password_hash)
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(user_id: str, password_hash: str | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode = {"sub": user_id, "exp": expire, "type": "refresh", "jti": str(uuid4())}
    if password_hash is not None:
        to_encode["pwh"] = password_fingerprint(password_hash)
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_token_pair(user) -> dict:
    uid = str(user.id)
    return {
        "access_token": create_access_token(uid, user.password_hash),
        "refresh_token": create_refresh_token(uid, user.password_hash),
    }


def _create_reset_token(user_id: str, password_hash: str | None = None) -> str:
    """Jeton de réinitialisation (60 min), à usage unique de fait.

    Il porte l'empreinte du mot de passe actuel: dès que le mot de passe est
    changé, le lien (même encore dans sa fenêtre de validité) ne marche plus.
    """
    expire = datetime.now(timezone.utc) + timedelta(minutes=60)
    to_encode = {"sub": user_id, "exp": expire, "type": "reset", "jti": str(uuid4()),
                 "pwh": password_fingerprint(password_hash)}
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
