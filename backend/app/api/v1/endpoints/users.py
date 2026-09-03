from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.dependencies import AuthenticatedPrincipal, get_current_user
from backend.app.api.v1.schemas.dtos import UserCreateDTO, UserResponseDTO
from backend.app.application.use_cases.user_service import UserService
from backend.app.core.errors import AnvikshikiDomainError
from backend.app.infrastructure.database.session import get_db

router = APIRouter(prefix="/users", tags=["Identity"])


def _response(user, access_token: str | None = None) -> UserResponseDTO:
    return UserResponseDTO(user_id=user.id, username=user.username, created_at=user.created_at, access_token=access_token)


@router.post("", response_model=UserResponseDTO, status_code=201)
async def create_user(payload: UserCreateDTO, db: AsyncSession = Depends(get_db)):
    user, access_token = await UserService(db).create_user(payload.username)
    return _response(user, access_token)


@router.get("/{user_id}", response_model=UserResponseDTO)
async def get_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedPrincipal | None = Depends(get_current_user),
):
    if current_user is not None and current_user.user_id != user_id:
        raise HTTPException(status_code=403, detail="The authenticated user does not own this resource.")
    user = await UserService(db).get_user(user_id)
    if not user:
        raise AnvikshikiDomainError(f"User {user_id} not found.", status_code=404)
    return _response(user)
