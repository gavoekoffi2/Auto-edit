import hashlib
import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.models.user import User
from app.schemas.user import (
    UserCreate, UserLogin, UserResponse, TokenResponse, TokenRefresh,
    PasswordResetRequest, PasswordResetConfirm, PasswordChange,
)
from app.services.auth import (
    hash_password,
    verify_password,
    create_token_pair,
    decode_token,
    token_matches_password,
)
from app.api.deps import get_current_user
from app.services.rate_limiter import (
    check_rate_limit, clear_rate_limit, record_rate_limit_hit,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Limites anti brute-force. En Afrique de l'Ouest, beaucoup d'utilisateurs
# sortent par la même IP (NAT des opérateurs mobiles): une limite par IP seule
# et comptant les connexions RÉUSSIES bloquait des inconnus entre eux. On
# compte donc uniquement les ÉCHECS, par couple IP+email (anti brute-force
# ciblé) et par IP avec un plafond large (anti credential-stuffing).
LOGIN_FAILS_PER_ACCOUNT = 5
LOGIN_FAILS_PER_IP = 30
LOGIN_WINDOW_S = 900


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _hash_email(email: str) -> str:
    """Hash partiel pour logger un email sans l'exposer en clair."""
    return hashlib.sha256(email.encode()).hexdigest()[:10]


def _tokens_for(user: User) -> TokenResponse:
    access, refresh = create_token_pair(user)
    return TokenResponse(access_token=access, refresh_token=refresh)


async def _load_user(db: AsyncSession, user_id) -> User | None:
    try:
        uid = UUID(str(user_id))
    except (ValueError, TypeError, AttributeError):
        return None
    result = await db.execute(select(User).where(User.id == uid))
    return result.scalar_one_or_none()


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
        full_name=data.full_name,
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError:
        # Deux inscriptions simultanées avec le même email: la contrainte
        # UNIQUE tranche — on répond 409 au lieu d'une 500.
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Un compte existe déjà avec cet email. Connecte-toi ou réinitialise ton mot de passe.",
        )

    logger.info("New user signup: user_id=%s email=%s", user.id, _hash_email(data.email))
    return _tokens_for(user)


@router.post("/login", response_model=TokenResponse)
async def login(data: UserLogin, request: Request, db: AsyncSession = Depends(get_db)):
    client_ip = _client_ip(request)
    account_key = f"login_fail:{client_ip}:{_hash_email(data.email)}"
    ip_key = f"login_fail_ip:{client_ip}"
    # Vérifie les plafonds SANS incrémenter: seuls les échecs comptent.
    await check_rate_limit(account_key, max_attempts=LOGIN_FAILS_PER_ACCOUNT,
                           window_seconds=LOGIN_WINDOW_S, increment=False)
    await check_rate_limit(ip_key, max_attempts=LOGIN_FAILS_PER_IP,
                           window_seconds=LOGIN_WINDOW_S, increment=False)

    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(data.password, user.password_hash):
        logger.warning("Failed login attempt email=%s ip=%s", _hash_email(data.email), client_ip)
        await record_rate_limit_hit(account_key, window_seconds=LOGIN_WINDOW_S)
        await record_rate_limit_hit(ip_key, window_seconds=LOGIN_WINDOW_S)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ce compte est désactivé. Contacte le support.",
        )

    await clear_rate_limit(account_key)
    logger.info("User login: user_id=%s", user.id)
    return _tokens_for(user)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(data: TokenRefresh, db: AsyncSession = Depends(get_db)):
    from app.services.auth import is_token_revoked

    invalid = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Session expirée. Reconnecte-toi.",
    )
    payload = decode_token(data.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise invalid

    # Bloque les refresh tokens revoques (logout)
    jti = payload.get("jti")
    if jti and await is_token_revoked(jti):
        raise invalid

    user = await _load_user(db, payload.get("sub"))
    if not user or not user.is_active:
        raise invalid
    # Mot de passe changé depuis l'émission du token -> session révoquée.
    if not token_matches_password(payload, user.password_hash):
        raise invalid

    # Pas de révocation à la rotation: le frontend peut rafraîchir en
    # parallèle (plusieurs onglets, upload + intercepteur) avec le MÊME refresh
    # token; le révoquer déconnecterait l'utilisateur en plein upload.
    return _tokens_for(user)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(data: TokenRefresh):
    """Revoke a refresh token (logout).

    Pas besoin d'access token valide: un utilisateur dont l'access token vient
    d'expirer doit quand même pouvoir révoquer sa session. Posséder le refresh
    token suffit à prouver qu'on a le droit de le révoquer.
    """
    from app.services.auth import revoke_token
    payload = decode_token(data.refresh_token)
    if payload and payload.get("type") == "refresh":
        jti = payload.get("jti")
        exp = payload.get("exp")
        ttl = max(0, int(exp - datetime.now(timezone.utc).timestamp())) if exp else 0
        if jti and ttl > 0:
            await revoke_token(jti, ttl)
    return {"message": "Déconnecté."}


@router.post("/password-change", response_model=TokenResponse)
async def change_password(
    data: PasswordChange,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Change le mot de passe et renvoie une NOUVELLE paire de tokens.

    Toutes les autres sessions (autres appareils, token volé) sont révoquées
    puisque leur empreinte de mot de passe ne correspond plus.
    """
    await check_rate_limit(f"pw_change:{current_user.id}", max_attempts=10, window_seconds=900)
    if not verify_password(data.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mot de passe actuel incorrect.",
        )

    current_user.password_hash = hash_password(data.new_password)
    current_user.updated_at = datetime.now(timezone.utc)
    await db.flush()

    logger.info("Password changed for user %s", current_user.id)
    return _tokens_for(current_user)


@router.post("/password-reset/request")
async def request_password_reset(
    data: PasswordResetRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Request a password reset. Always returns success (prevents email enumeration)."""
    await check_rate_limit(f"pw_reset:{_client_ip(request)}", max_attempts=5, window_seconds=900)
    # Évite d'inonder une même boîte mail, quelle que soit l'IP.
    await check_rate_limit(f"pw_reset_email:{_hash_email(data.email)}", max_attempts=3,
                           window_seconds=3600)

    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()

    if user and user.is_active:
        from app.services.auth import _create_reset_token
        from app.services.email import send_password_reset_email
        from app.config import settings

        token = _create_reset_token(str(user.id), user.password_hash)
        reset_url = f"{settings.PUBLIC_APP_URL.rstrip('/')}/reset-password?token={token}"
        # ATTENTION: ne JAMAIS logger le token ni l'URL contenant le token.
        # L'envoi (SMTP/HTTP) est bloquant: hors de la boucle async pour ne pas
        # geler toutes les autres requêtes pendant jusqu'à 15 s.
        sent = await run_in_threadpool(
            send_password_reset_email, to_email=data.email, reset_url=reset_url
        )
        logger.info("Password reset requested user_id=%s email=%s sent=%s",
                    user.id, _hash_email(data.email), sent)

    # Always return success to prevent email enumeration
    return {"message": "Si cet email correspond à un compte, un lien de réinitialisation vient d'être envoyé."}


@router.post("/password-reset/confirm")
async def confirm_password_reset(
    data: PasswordResetConfirm,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Confirm password reset with token."""
    await check_rate_limit(f"pw_reset_confirm:{_client_ip(request)}", max_attempts=10,
                           window_seconds=900)
    invalid = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Lien de réinitialisation invalide, expiré ou déjà utilisé. Refais une demande.",
    )
    payload = decode_token(data.token)
    if not payload or payload.get("type") != "reset":
        raise invalid

    user = await _load_user(db, payload.get("sub"))
    if not user or not user.is_active:
        raise invalid
    # Usage unique: le lien est lié au mot de passe qu'il remplace.
    if not token_matches_password(payload, user.password_hash):
        raise invalid

    user.password_hash = hash_password(data.new_password)
    user.updated_at = datetime.now(timezone.utc)
    await db.flush()

    logger.info("Password reset completed for user %s", user.id)
    return {"message": "Mot de passe réinitialisé. Tu peux te connecter."}
