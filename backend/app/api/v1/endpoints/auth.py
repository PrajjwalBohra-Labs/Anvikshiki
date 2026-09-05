from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.dependencies import AuthenticatedPrincipal, get_current_user
from backend.app.api.v1.schemas.dtos import UserResponseDTO, UsernameAuthenticationDTO
from backend.app.application.use_cases.auth_service import AuthService
from backend.app.infrastructure.database.session import get_db


router = APIRouter(prefix="/auth", tags=["Authentication"])


def _response(user, access_token: str) -> UserResponseDTO:
    return UserResponseDTO(
        user_id=user.id,
        username=user.username,
        created_at=user.created_at,
        access_token=access_token,
    )


@router.post("/login", response_model=UserResponseDTO)
async def authenticate_username(
    payload: UsernameAuthenticationDTO,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate an existing identity by username and issue a session."""
    service = AuthService(db)
    user = await service.authenticate_username(payload.username)
    if user is None:
        raise HTTPException(status_code=404, detail="Username is not registered.")
    return _response(user, await service.issue_session(user))


@router.get("/me")
async def get_current_identity(
    current_user: Optional[AuthenticatedPrincipal] = Depends(get_current_user),
):
    if current_user is None:
        raise HTTPException(status_code=401, detail="Bearer authentication is required.")
    return {"user_id": current_user.user_id, "username": current_user.username}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    authorization: Optional[str] = Header(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[AuthenticatedPrincipal] = Depends(get_current_user),
):
    if current_user is None or not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication is required.")
    await AuthService(db).revoke(authorization[7:].strip())
