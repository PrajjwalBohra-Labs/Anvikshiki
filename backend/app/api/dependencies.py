"""Shared HTTP authentication and ownership helpers."""

from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.application.use_cases.auth_service import AuthService
from backend.app.core.config import RuntimeProfile, settings
from backend.app.infrastructure.database.models import UserModel
from backend.app.infrastructure.database.session import get_db


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    user_id: str
    username: str


async def get_current_user(
    authorization: Optional[str] = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> Optional[AuthenticatedPrincipal]:
    # This mode is set only by the isolated test harness. There is no
    # unauthenticated fallback in development or production.
    if (
        settings.RUNTIME_PROFILE == RuntimeProfile.TEST
        and settings.AUTH_MODE == "test"
        and not authorization
    ):
        return None

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer authentication is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization[7:].strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer authentication is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user: Optional[UserModel] = await AuthService(db).authenticate(token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token is invalid or expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return AuthenticatedPrincipal(user_id=user.id, username=user.username)


def resolve_user_id(
    principal: Optional[AuthenticatedPrincipal],
    requested_user_id: Optional[str],
) -> str:
    if principal is None:
        if not requested_user_id:
            raise HTTPException(status_code=401, detail="Authentication is required.")
        return requested_user_id
    if requested_user_id is not None and requested_user_id != principal.user_id:
        raise HTTPException(status_code=403, detail="The authenticated user does not own this resource.")
    return principal.user_id
