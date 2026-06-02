import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
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
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.api.deps import get_current_user
from app.services.rate_limiter import check_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def signup(data: UserCreate, request: Request, db: AsyncSession = Depends(get_db)):
    # Rate limit signups by IP
    client_ip = request.client.host if request.client else "unknown"
    await check_rate_limit(f"signup:{client_ip}", max_attempts=10, window_seconds=3600)

    # Check if user exists
    result = await db.execute(select(User).where(User.email == data.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    user = User(
        email=data.email,
        password_hash=hash_password(data.password),
        full_name=data.full_name,
    )
    db.add(user)
    await db.flush()

    logger.info(f"New user signup: {data.email}")

    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.post("/login", response_model=TokenResponse)
async def login(data: UserLogin, request: Request, db: AsyncSession = Depends(get_db)):
    # Rate limit login by IP
    client_ip = request.client.host if request.client else "unknown"
    await check_rate_limit(f"login:{client_ip}", max_attempts=5, window_seconds=900)

    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(data.password, user.password_hash):
        logger.warning(f"Failed login attempt for: {data.email} from IP: {client_ip}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    logger.info(f"User login: {data.email}")

    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(data: TokenRefresh, db: AsyncSession = Depends(get_db)):
    from app.services.auth import is_token_revoked
    payload = decode_token(data.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    # Bloque les refresh tokens revoques (logout)
    jti = payload.get("jti")
    if jti and await is_token_revoked(jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token revoked",
        )

    user_id = payload.get("sub")

    # Verify user still exists and is active
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or deactivated",
        )

    return TokenResponse(
        access_token=create_access_token(user_id),
        refresh_token=create_refresh_token(user_id),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(data: TokenRefresh, current_user: User = Depends(get_current_user)):
    """Revoke a refresh token (logout).

    Le client doit ensuite supprimer ses tokens du localStorage.
    L'access token (15 min) expirera de lui-meme.
    """
    from app.services.auth import revoke_token
    payload = decode_token(data.refresh_token)
    if payload and payload.get("type") == "refresh":
        jti = payload.get("jti")
        exp = payload.get("exp")
        ttl = max(0, int(exp - datetime.now(timezone.utc).timestamp())) if exp else 0
        if jti and ttl > 0:
            await revoke_token(jti, ttl)
    return {"message": "Logged out"}


@router.post("/password-change")
async def change_password(
    data: PasswordChange,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Change password for authenticated user."""
    if not verify_password(data.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    current_user.password_hash = hash_password(data.new_password)
    current_user.updated_at = datetime.now(timezone.utc)
    await db.flush()

    logger.info(f"Password changed for user {current_user.id}")
    return {"message": "Password changed successfully."}


@router.post("/password-reset/request")
async def request_password_reset(
    data: PasswordResetRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Request a password reset. Always returns success (prevents email enumeration)."""
    client_ip = request.client.host if request.client else "unknown"
    await check_rate_limit(f"pw_reset:{client_ip}", max_attempts=3, window_seconds=900)

    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()

    if user and user.is_active:
        # Generate a short-lived reset token (15 min)
        from app.services.auth import _create_reset_token
        from app.services.email import send_password_reset_email
        from app.config import settings

        token = _create_reset_token(str(user.id))
        reset_url = f"{settings.PUBLIC_APP_URL.rstrip('/')}/reset-password?token={token}"
        # ATTENTION: ne JAMAIS logger le token ni l'URL contenant le token.
        sent = send_password_reset_email(to_email=data.email, reset_url=reset_url)
        logger.info("Password reset requested user_id=%s email=%s sent=%s",
                    user.id, _hash_email(data.email), sent)

    # Always return success to prevent email enumeration
    return {"message": "If that email is registered, a reset link has been sent."}


def _hash_email(email: str) -> str:
    """Hash partiel pour logger un email sans l'exposer en clair."""
    import hashlib
    return hashlib.sha256(email.encode()).hexdigest()[:10]


@router.post("/password-reset/confirm")
async def confirm_password_reset(
    data: PasswordResetConfirm,
    db: AsyncSession = Depends(get_db),
):
    """Confirm password reset with token."""
    payload = decode_token(data.token)
    if not payload or payload.get("type") != "reset":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    user.password_hash = hash_password(data.new_password)
    user.updated_at = datetime.now(timezone.utc)
    await db.flush()

    logger.info(f"Password reset completed for user {user.id}")
    return {"message": "Password has been reset successfully."}
