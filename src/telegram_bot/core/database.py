from collections.abc import AsyncGenerator
# a type hint indicating that a function will yield objects async over time

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,  # tools used to spawn individual , short-lived session workspace to run queries 
    create_async_engine
)

from sqlalchemy.orm import DeclarativeBase

from telegram_bot.core.config import get_settings


settings = get_settings()
# imports application configuration settings like your secret DB credentials

# creates the core engine object that handles actual network connections to the DB using async drivers 
engine = create_async_engine(
    settings.database_url,
    echo=False, # if set to True, it logs every single raw SQL quer to the console
    pool_pre_ping=True, 
    connect_args={"ssl":"require"} # forces the connection be encypted using SSL, 
)


AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    '''
    the base class used to map python classes directly to database tables (ORM)
    
    '''
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:

    async with AsyncSessionLocal() as session:
        yield session

async def create_tables():
    '''
    create all the tables!
    '''
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)