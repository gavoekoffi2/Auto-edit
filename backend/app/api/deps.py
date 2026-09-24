from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.models.user import User
from app.services.auth import decode_token, token_matches_password
from app.config import settings

security = HTTPBearer()


async def resolve_access_token_user(db: AsyncSession, token: str | None) -> User:
    """Utilisateur actif porté par un ACCESS token, sinon HTTP 401/403.

    Source unique pour l'API (header Bearer) ET les routes média (token en
    query string, car <video> ne peut pas envoyer de header). Un token émis
    avant un changement de mot de passe est refusé.
    """
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Session expirée. Reconnecte-toi.",
    )
    payload = decode_token(token) if token else None
    if payload is None or payload.get("type") != "access":
        raise unauthorized

    try:
        user_uuid = UUID(str(payload.get("sub")))
    except (ValueError, TypeError, AttributeError):
        # Un `sub` malformé doit répondre 401, pas une 500 interne.
        raise unauthorized

    result = await db.execute(select(User).where(User.id == user_uuid))
    user = result.scalar_one_or_none()
    if user is None:
        raise unauthorized
    if not token_matches_password(payload, user.password_hash):
        raise unauthorized
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ce compte est désactivé. Contacte le support.",
        )
    return user


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    return await resolve_access_token_user(db, credentials.credentials)


async def get_media_user(
    db: AsyncSession,
    credentials: HTTPAuthorizationCredentials | None,
    access_token: str | None,
) -> User:
    """Auth des routes média: header Bearer OU ``?access_token=``."""
    token = credentials.credentials if credentials else access_token
    return await resolve_access_token_user(db, token)


async def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    configured_admin = current_user.email.lower() in settings.admin_email_set
    if not (getattr(current_user, "is_admin", False) or configured_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


async def get_current_super_admin(current_user: User = Depends(get_current_user)) -> User:
    configured_founder = current_user.email.lower() in settings.admin_email_set
    if not (getattr(current_user, "is_super_admin", False) or configured_founder):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super administrator access required",
        )
    return current_user
