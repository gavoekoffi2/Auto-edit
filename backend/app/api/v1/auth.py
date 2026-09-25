import hashlib
import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import (
    UserCreate, UserLogin, UserResponse, TokenResponse, TokenRefresh,
    PasswordResetRequest, PasswordResetConfirm, PasswordChange,
)
from app.services.auth import (
    hash_password,
    verify_password_constant_time,
    create_token_pair,
    decode_token,
    token_matches_password,
)
from app.api.deps import get_current_user
from app.services.rate_limiter import (
    check_rate_limit,
    ensure_not_limited,
    record_failure,
    reset_counter,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Échecs de connexion tolérés avant blocage temporaire (fenêtre de 15 min).
# Par EMAIL: protège chaque compte du brute-force. Par IP: large, car une IP
# d'opérateur mobile (CGNAT) est partagée par énormément d'utilisateurs.
LOGIN_WINDOW_S = 900
LOGIN_MAX_FAILURES_PER_EMAIL = 8
LOGIN_MAX_FAILURES_PER_IP = 50


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _hash_email(email: str) -> str:
    """Hash partiel pour logger un email sans l'exposer en clair."""
    return hashlib.sha256(email.encode()).hexdigest()[:10]


def _parse_uuid(value) -> UUID | None:
    try:
        return UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        return None


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def signup(data: UserCreate, request: Request, db: AsyncSession = Depends(get_db)):
    await check_rate_limit(f"signup:{_client_ip(request)}", max_attempts=20, window_seconds=3600)

    result = await db.execute(select(User).where(User.email == data.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Un compte existe déjà avec cet email. Connecte-toi ou réinitialise ton mot de passe.",
        )

    user = User(
        email=data.email,
        password_hash=hash_password(data.password),
        full_name=data.full_name or None,
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError:
        # Deux inscriptions simultanées avec le même email.
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Un compte existe déjà avec cet email.",
        )

    logger.info("New user signup: user_id=%s email=%s", user.id, _hash_email(data.email))
    return TokenResponse(**create_token_pair(user))


@router.post("/login", response_model=TokenResponse)
async def login(data: UserLogin, request: Request, db: AsyncSession = Depends(get_db)):
    ip_key = f"login_ip:{_client_ip(request)}"
    email_key = f"login_email:{_hash_email(data.email)}"
    # Seuls les ÉCHECS sont comptés: les connexions réussies ne bloquent
    # personne (important derrière les NAT d'opérateurs mobiles).
    await ensure_not_limited(email_key, LOGIN_MAX_FAILURES_PER_EMAIL)
    await ensure_not_limited(ip_key, LOGIN_MAX_FAILURES_PER_IP)

    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()

    password_ok = verify_password_constant_time(
        data.password, user.password_hash if user else None)
    if not user or not password_ok:
        await record_failure(email_key, LOGIN_WINDOW_S)
        await record_failure(ip_key, LOGIN_WINDOW_S)
        logger.warning("Failed login for email=%s from ip=%s",
                       _hash_email(data.email), _client_ip(request))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ce compte est désactivé. Contacte le support.",
        )

    await reset_counter(email_key)
    logger.info("User login: user_id=%s", user.id)
    return TokenResponse(**create_token_pair(user))


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(data: TokenRefresh, db: AsyncSession = Depends(get_db)):
    from app.services.auth import is_token_revoked
    payload = decode_token(data.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expirée. Reconnecte-toi.",
        )

    jti = payload.get("jti")
    if jti and await is_token_revoked(jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expirée. Reconnecte-toi.",
        )

    user_uuid = _parse_uuid(payload.get("sub"))
    user = None
    if user_uuid is not None:
        result = await db.execute(select(User).where(User.id == user_uuid))
        user = result.scalar_one_or_none()
    if not user or not user.is_active or not token_matches_password(payload, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expirée. Reconnecte-toi.",
        )

    return TokenResponse(**create_token_pair(user))


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(data: TokenRefresh):
    """Révoque un refresh token (déconnexion).

    Ne dépend PAS de l'access token: un utilisateur dont l'access token a
    expiré doit quand même pouvoir fermer proprement sa session.
    """
    from app.services.auth import revoke_token
    payload = decode_token(data.refresh_token)
    if payload and payload.get("type") == "refresh":
        jti = payload.get("jti")
        exp = payload.get("exp")
        ttl = max(0, int(exp - datetime.now(timezone.utc).timestamp())) if exp else 0
        if jti and ttl > 0:
            await revoke_token(jti, ttl)
    return {"message": "Déconnecté"}


@router.post("/password-change", response_model=TokenResponse)
async def change_password(
    data: PasswordChange,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Change le mot de passe. Déconnecte toutes les AUTRES sessions et
    renvoie une nouvelle paire de jetons pour la session courante."""
    key = f"pw_change:{current_user.id}"
    await ensure_not_limited(key, 10)
    if not verify_password_constant_time(data.current_password, current_user.password_hash):
        await record_failure(key, 900)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le mot de passe actuel est incorrect.",
        )

    current_user.password_hash = hash_password(data.new_password)
    current_user.updated_at = datetime.now(timezone.utc)
    await db.flush()

    logger.info("Password changed for user %s", current_user.id)
    return TokenResponse(**create_token_pair(current_user))


@router.post("/password-reset/request")
async def request_password_reset(
    data: PasswordResetRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Demande de réinitialisation. Réponse identique que l'email existe ou non."""
    await check_rate_limit(f"pw_reset:{_client_ip(request)}", max_attempts=10, window_seconds=900)
    await check_rate_limit(f"pw_reset_email:{_hash_email(data.email)}", max_attempts=3,
                           window_seconds=3600)

    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()

    if user and user.is_active:
        from app.services.auth import _create_reset_token
        from app.services.email import send_password_reset_email

        token = _create_reset_token(str(user.id), user.password_hash)
        reset_url = f"{settings.PUBLIC_APP_URL.rstrip('/')}/reset-password?token={token}"
        # ATTENTION: ne JAMAIS logger le token ni l'URL contenant le token.
        # L'envoi (SMTP/HTTP bloquant) part dans un thread: il ne doit pas
        # geler la boucle asynchrone de l'API.
        sent = await run_in_threadpool(
            send_password_reset_email, to_email=data.email, reset_url=reset_url)
        logger.info("Password reset requested user_id=%s email=%s sent=%s",
                    user.id, _hash_email(data.email), sent)

    return {"message": "Si cet email correspond à un compte, un lien de réinitialisation vient d'être envoyé."}


@router.post("/password-reset/confirm")
async def confirm_password_reset(
    data: PasswordResetConfirm,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Confirme la réinitialisation avec le jeton reçu par email."""
    await check_rate_limit(f"pw_reset_confirm:{_client_ip(request)}", max_attempts=20,
                           window_seconds=900)
    invalid = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Lien invalide ou expiré. Refais une demande de réinitialisation.",
    )
    payload = decode_token(data.token)
    if not payload or payload.get("type") != "reset":
        raise invalid

    user_uuid = _parse_uuid(payload.get("sub"))
    if user_uuid is None:
        raise invalid
    result = await db.execute(select(User).where(User.id == user_uuid))
    user = result.scalar_one_or_none()

    # L'empreinte du mot de passe rend le lien à usage unique: après une
    # réinitialisation réussie, le même lien ne fonctionne plus.
    if not user or not user.is_active or "pwh" not in payload \
            or not token_matches_password(payload, user.password_hash):
        raise invalid

    user.password_hash = hash_password(data.new_password)
    user.updated_at = datetime.now(timezone.utc)
    await db.flush()

    logger.info(f"Password reset completed for user {user.id}")
    return {"message": "Mot de passe réinitialisé. Tu peux te connecter."}
