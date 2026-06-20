"""
Auth router – handles user registration and login.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.database import get_db
from backend.models.user import User
from backend.schemas.auth_schemas import (
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
    UserResponse,
)
from backend.services.auth_service import (
    create_token,
    hash_password,
    verify_password,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ── POST /auth/register ───────────────────────────────────────────────────────

@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
async def register(
    payload: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> RegisterResponse:
    """
    Create a new user account.

    - **email**: must be a valid, unique email address.
    - **username**: 3-100 chars, alphanumeric / underscore / hyphen; must be unique.
    - **password**: at least 8 chars, one digit, one uppercase letter.
    """
    # ── Duplicate check ───────────────────────────────────────────────────────
    existing = await db.execute(
        select(User).where(
            (User.email == payload.email) | (User.username == payload.username)
        )
    )
    if existing.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email or username already exists.",
        )

    # ── Create user ───────────────────────────────────────────────────────────
    new_user = User(
        email=payload.email,
        username=payload.username,
        password_hash=hash_password(payload.password),
    )
    db.add(new_user)

    try:
        await db.flush()  # get the generated UUID before commit
        await db.refresh(new_user)
    except IntegrityError as exc:
        await db.rollback()
        logger.error("IntegrityError during registration: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email or username already exists.",
        ) from exc

    logger.info("New user registered: %s (id=%s)", new_user.email, new_user.id)

    return RegisterResponse(user=UserResponse.model_validate(new_user))


# ── POST /auth/login ──────────────────────────────────────────────────────────

@router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    summary="Login and receive an access token",
)
async def login(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    """
    Authenticate a user and return a JWT bearer token.

    - **email**: registered email address.
    - **password**: account password.
    """
    # ── Fetch user ────────────────────────────────────────────────────────────
    result = await db.execute(select(User).where(User.email == payload.email))
    user: User | None = result.scalars().first()

    _invalid_creds = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if user is None:
        raise _invalid_creds

    if not verify_password(payload.password, user.password_hash):
        raise _invalid_creds

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deactivated. Contact support.",
        )

    # ── Issue token ───────────────────────────────────────────────────────────
    access_token, expires_in = create_token(
        user_id=user.id,
        email=user.email,
        role=user.role.value,
    )

    logger.info("User logged in: %s (id=%s)", user.email, user.id)

    return LoginResponse(
        user=UserResponse.model_validate(user),
        token=TokenResponse(access_token=access_token, expires_in=expires_in),
    )


# ── GET /auth/google/login ────────────────────────────────────────────────────

import urllib.parse
from fastapi.responses import RedirectResponse
from backend.config import get_settings
import httpx
import json

@router.get(
    "/google/login",
    status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    summary="Redirect to Google OAuth consent screen",
)
async def google_login():
    settings = get_settings()
    google_auth_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={settings.GOOGLE_CLIENT_ID}&"
        f"redirect_uri={settings.GOOGLE_REDIRECT_URI}&"
        f"response_type=code&"
        f"scope=openid%20email%20profile"
    )
    return RedirectResponse(url=google_auth_url)


# ── GET /auth/google/callback ─────────────────────────────────────────────────

@router.get(
    "/google/callback",
    summary="Google OAuth callback endpoint",
)
async def google_callback(
    code: str,
    db: AsyncSession = Depends(get_db)
):
    settings = get_settings()
    
    # 1. Exchange code for token
    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
    }
    
    async with httpx.AsyncClient() as client:
        token_response = await client.post(token_url, data=data)
        token_data = token_response.json()
        
    access_token = token_data.get("access_token")
    if not access_token:
        logger.error(f"Google token error: {token_data}")
        raise HTTPException(status_code=400, detail="Failed to retrieve access token from Google")
        
    # 2. Get user info
    userinfo_url = "https://www.googleapis.com/oauth2/v3/userinfo"
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient() as client:
        userinfo_response = await client.get(userinfo_url, headers=headers)
        user_info = userinfo_response.json()
        
    email = user_info.get("email")
    name = user_info.get("name") or email.split("@")[0]
    
    if not email:
        raise HTTPException(status_code=400, detail="Google authentication failed: Email not provided")
        
    # 3. Check if user exists, otherwise create
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalars().first()
    
    if not user:
        import secrets
        random_password = secrets.token_urlsafe(32)
        base_username = email.split("@")[0]
        # Ensure unique username
        username = f"{base_username}_{secrets.token_hex(2)}"
        
        user = User(
            email=email,
            username=username,
            password_hash=hash_password(random_password),
            is_active=True
        )
        db.add(user)
        try:
            await db.flush()
            await db.refresh(user)
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            logger.error("IntegrityError during Google registration: %s", exc)
            raise HTTPException(status_code=400, detail="Could not create user account") from exc

    # 4. Issue our JWT token
    jwt_token, expires_in = create_token(
        user_id=user.id,
        email=user.email,
        role=user.role.value,
    )
    
    logger.info("Google User logged in: %s (id=%s)", user.email, user.id)
    
    # 5. Redirect back to frontend with token and user data
    user_dict = {
        "id": str(user.id),
        "email": user.email,
        "username": user.username,
        "role": user.role.value,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if user.created_at else None
    }
    
    user_json = json.dumps(user_dict)
    user_encoded = urllib.parse.quote(user_json)
    
    frontend_redirect_url = f"http://localhost:5173/login?token={jwt_token}&user={user_encoded}"
    return RedirectResponse(url=frontend_redirect_url)
