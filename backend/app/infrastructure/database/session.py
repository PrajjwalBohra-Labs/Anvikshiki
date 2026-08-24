from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from backend.app.core.config import settings, RuntimeProfile

# If testing, use an in-memory SQLite database to avoid requiring a live Postgres instance for unit tests
if settings.RUNTIME_PROFILE == RuntimeProfile.TEST:
    engine_url = "sqlite+aiosqlite:///:memory:"
else:
    engine_url = settings.DATABASE_URL

engine = create_async_engine(
    engine_url,
    echo=settings.DEBUG and settings.RUNTIME_PROFILE != RuntimeProfile.TEST,
    future=True,
    pool_pre_ping=True
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

class Base(DeclarativeBase):
    pass

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()