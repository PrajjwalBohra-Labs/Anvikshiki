import asyncio

from backend.app.infrastructure.database import models as _models  # noqa: F401
from backend.app.infrastructure.database.session import Base, engine


async def main() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    await engine.dispose()


asyncio.run(main())
