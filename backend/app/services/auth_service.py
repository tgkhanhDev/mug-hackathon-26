"""
Auth service — JWT token generation and password hashing.

Stub implementation for Stage 2. Provides:
- Password hashing (bcrypt)
- JWT access token generation
- JWT refresh token generation
- Token verification
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings
from app.models.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
)
from app.models.user import UserInDB
from app.repositories.user_repository import UserRepository
from app.utils.exceptions import (
    DuplicateException,
    UnauthorizedException,
    NotFoundException,
)

logger = logging.getLogger(__name__)

# ── Password hashing context ──────────────────────────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    """Authentication service — register, login, JWT management."""

    def __init__(self):
        self._repo = UserRepository()

    # ── Register ───────────────────────────────────────────────

    async def register(self, data: RegisterRequest) -> TokenResponse:
        """
        Register a new user with password.

        1. Check username uniqueness
        2. Hash password
        3. Create user document with interest_tags
        4. Return JWT token pair
        """
        existing = await self._repo.find_by_username(data.username)
        if existing:
            raise DuplicateException("User", "username")

        # Hash password
        hashed_pw = pwd_context.hash(data.password)

        now = datetime.utcnow()
        doc = UserInDB(
            username=data.username,
            email=data.email,
            password_hash=hashed_pw,
            interest_tags=data.interest_tags,
            interest_vector=[],  # Will be populated by scheduler or onboarding flow
            created_at=now,
            updated_at=now,
        )

        user_id = await self._repo.insert_one(doc.model_dump())
        logger.info(f"✅ Registered user: {user_id} — {data.username}")

        # Generate token pair
        return self._create_token_pair(user_id, data.username)

    # ── Login ──────────────────────────────────────────────────

    async def login(self, data: LoginRequest) -> TokenResponse:
        """
        Authenticate user and return JWT token pair.

        1. Find user by username
        2. Verify password
        3. Return JWT token pair
        """
        user = await self._repo.find_by_username(data.username)
        if not user:
            raise UnauthorizedException("Invalid username or password")

        if not pwd_context.verify(data.password, user.get("password_hash", "")):
            raise UnauthorizedException("Invalid username or password")

        return self._create_token_pair(user["id"], user["username"])

    # ── Token Management ───────────────────────────────────────

    @staticmethod
    def _create_token_pair(user_id: str, username: str) -> TokenResponse:
        """Generate access + refresh token pair."""
        access_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        refresh_expires = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

        access_token = _create_jwt(
            data={"sub": user_id, "username": username, "type": "access"},
            expires_delta=access_expires,
        )
        refresh_token = _create_jwt(
            data={"sub": user_id, "username": username, "type": "refresh"},
            expires_delta=refresh_expires,
        )

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user_id=user_id,
            username=username,
        )

    @staticmethod
    def verify_access_token(token: str) -> dict:
        """
        Verify and decode an access token.
        Returns the payload dict if valid, raises UnauthorizedException otherwise.
        """
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
            )
            if payload.get("type") != "access":
                raise UnauthorizedException("Invalid token type")
            return payload
        except JWTError:
            raise UnauthorizedException("Invalid or expired token")

    async def refresh_tokens(self, refresh_token: str) -> TokenResponse:
        """
        Use a refresh token to get a new token pair.
        """
        try:
            payload = jwt.decode(
                refresh_token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
            )
            if payload.get("type") != "refresh":
                raise UnauthorizedException("Invalid token type")

            user_id = payload.get("sub")
            username = payload.get("username")

            if not user_id or not username:
                raise UnauthorizedException("Invalid refresh token payload")

            return self._create_token_pair(user_id, username)

        except JWTError:
            raise UnauthorizedException("Invalid or expired refresh token")


# ── Module-level helpers ───────────────────────────────────────

def _create_jwt(data: dict, expires_delta: timedelta) -> str:
    """Create a signed JWT token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    return jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
