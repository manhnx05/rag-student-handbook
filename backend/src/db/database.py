from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncEngine
from sqlalchemy.orm import declarative_base
from src.core.config import settings

engine: AsyncEngine | None = None
AsyncSessionLocal = None
Base = declarative_base()

def setup_db():
    global engine, AsyncSessionLocal
    engine = create_async_engine(
        settings.async_database_url, 
        echo=False,
        pool_size=20,
        max_overflow=10,
        pool_pre_ping=True
    )
    AsyncSessionLocal = async_sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )

async def close_db():
    global engine
    if engine is not None:
        await engine.dispose()

async def get_db():
    if AsyncSessionLocal is None:
        setup_db()
    async with AsyncSessionLocal() as session:
        yield session
