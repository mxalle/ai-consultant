from collections.abc import AsyncGenerator, Iterator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401  -- registers the tables on Base.metadata
from app.config import settings
from app.database import Base

# Tests run on in-memory SQLite so they do not need Docker/Postgres.
TEST_DATABASE_URL = "sqlite+aiosqlite://"

OWNER_CHAT_ID = 1000


@pytest.fixture(autouse=True)
def settings_for_tests() -> Iterator[None]:
    """Pin the settings handlers read, whatever the local `.env` says."""
    saved = settings.model_dump()
    settings.owner_chat_id = OWNER_CHAT_ID
    settings.business_name = "Барбершоп «Тест»"
    settings.booking_url = "https://booking.example/test"
    settings.rate_limit_per_hour = 30
    settings.llm_api_key = "test-key"
    settings.llm_model = "test-model"
    yield
    for name, value in saved.items():
        setattr(settings, name, value)


@pytest_asyncio.fixture
async def engine() -> AsyncGenerator[AsyncEngine, None]:
    engine = create_async_engine(
        TEST_DATABASE_URL,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    async with session_factory() as session:
        yield session
