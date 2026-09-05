import asyncio
from uuid import uuid4

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from backend.app.application.use_cases.auth_service import AuthService, _hash_token
from backend.app.application.use_cases.user_service import UserService
from backend.app.core.config import settings
from backend.app.infrastructure.database.models import AuthSessionModel
from backend.app.infrastructure.database.session import AsyncSessionLocal, Base, engine
from backend.app.main import app


async def main():
    print("settings", settings.RUNTIME_PROFILE, settings.AUTH_MODE)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as session:
        user, token = await UserService(session).create_user("probe-a-" + uuid4().hex)
        other, other_token = await UserService(session).create_user("probe-b-" + uuid4().hex)
        print("created", user.id, repr(token), _hash_token(token), other.id, repr(other_token))
        authenticated = await AuthService(session).authenticate(token)
        print("direct auth", authenticated and authenticated.id)
        rows = (await session.execute(select(AuthSessionModel))).scalars().all()
        print("rows", [(row.user_id, row.token_hash == _hash_token(token), row.expires_at) for row in rows])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first = await client.post(
            "/api/v1/research/jobs",
            json={"query": "What is knowledge?", "idempotency_key": "unauth"},
        )
        print("unauth", first.status_code, first.text)
        response = await client.post(
            "/api/v1/research/jobs",
            headers={"Authorization": "Bearer " + token, "X-Request-ID": "11111111-1111-4111-8111-111111111111"},
            json={"query": "What is knowledge?", "idempotency_key": "probe"},
        )
        print("http", response.status_code, response.text)
    await engine.dispose()


asyncio.run(main())
