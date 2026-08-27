from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from backend.app.application.use_cases.auth_service import AuthService
from backend.app.core.errors import AnvikshikiDomainError
from backend.app.infrastructure.database.models import UserModel


class UserService:
    """Owns the local identity lifecycle without pretending to be authentication."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_user(self, username: str) -> tuple[UserModel, str]:
        existing = await self.session.execute(select(UserModel).where(UserModel.username == username))
        if existing.scalars().first():
            raise AnvikshikiDomainError("Username is already registered.", status_code=409)
        user = UserModel(username=username)
        self.session.add(user)
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise AnvikshikiDomainError("Username is already registered.", status_code=409) from exc
        await self.session.refresh(user)
        token = await AuthService(self.session).issue_session(user)
        return user, token

    async def get_user(self, user_id: str) -> Optional[UserModel]:
        return await self.session.get(UserModel, user_id)
