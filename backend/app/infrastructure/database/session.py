from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool
from sqlalchemy.orm import DeclarativeBase
from backend.app.core.config import settings, RuntimeProfile

# SQLite is reserved for isolated tests. Development and integration use the
# explicit PostgreSQL DATABASE_URL.
if settings.RUNTIME_PROFILE == RuntimeProfile.TEST:
    engine_url = settings.TEST_DATABASE_URL
else:
    engine_url = settings.DATABASE_URL

engine = create_async_engine(
    engine_url,
    echo=settings.DEBUG and settings.RUNTIME_PROFILE != RuntimeProfile.TEST,
    future=True,
    pool_pre_ping=True,
    poolclass=NullPool if settings.RUNTIME_PROFILE == RuntimeProfile.TEST else None,
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
