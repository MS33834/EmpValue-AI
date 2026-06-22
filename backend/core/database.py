"""
数据库连接与会话管理
默认使用 SQLite + aiosqlite（开发/演示），生产环境通过 DATABASE_URL 切换为 PostgreSQL。
"""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from core.config import get_settings

settings = get_settings()

DATABASE_URL = settings.database_url

engine = create_async_engine(
    DATABASE_URL,
    echo=settings.debug,
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖：获取数据库会话"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db() -> None:
    """创建所有数据表"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """关闭数据库连接"""
    await engine.dispose()
