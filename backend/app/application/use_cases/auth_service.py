"""Local bearer-session authentication for the HTTP API."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from backend.app.core.config import settings
from backend.app.infrastructure.database.models import AuthSessionModel, UserModel


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class AuthService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def issue_session(self, user: UserModel) -> str:
        token = secrets.token_urlsafe(32)
        auth_session = AuthSessionModel(
            user_id=user.id,
            token_hash=_hash_token(token),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=settings.AUTH_TOKEN_TTL_MINUTES),
        )
        self.session.add(auth_session)
        await self.session.commit()
        return token

    async def authenticate(self, token: str) -> UserModel | None:
        token_hash = _hash_token(token)
        result = await self.session.execute(
            select(AuthSessionModel)
            .where(
                AuthSessionModel.token_hash == token_hash,
                AuthSessionModel.expires_at > datetime.now(timezone.utc),
            )
            .options(selectinload(AuthSessionModel.user))
        )
        auth_session = result.scalars().first()
        return auth_session.user if auth_session else None

    async def revoke(self, token: str) -> bool:
        result = await self.session.execute(
            select(AuthSessionModel).where(AuthSessionModel.token_hash == _hash_token(token))
        )
        auth_session = result.scalars().first()
        if auth_session is None:
            return False
        await self.session.delete(auth_session)
        await self.session.commit()
        return True
