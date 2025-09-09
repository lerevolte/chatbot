from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from contextlib import asynccontextmanager
import logging

from bot.config import settings
from database.models import Base

logger = logging.getLogger(__name__)

# Создаем движок БД
engine = create_async_engine(
    settings.database_url,
    echo=settings.DEBUG,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600
)

# Создаем фабрику сессий
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def init_db():
    """Инициализация БД - создание таблиц"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("База данных инициализирована")

async def close_db():
    """Закрытие соединения с БД"""
    await engine.dispose()
    logger.info("Соединение с БД закрыто")

@asynccontextmanager
async def get_session():
    """Контекстный менеджер для работы с сессией"""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()