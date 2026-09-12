

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


from telegram_bot.core.security import hash_password, verify_password
from telegram_bot.models.user import User

async def get_user_by_username(db:AsyncSession, username:str)-> User | None:
    result = await db.execute(
        select(User).where(
            User.username == username
        )
    )

    return result.scalar_one_or_none()


async def register_user(
    db: AsyncSession,
    username: str,
    password: str,
) -> User:

    existing_user = await get_user_by_username(
        db,
        username,
    )

    if existing_user:
        raise ValueError("Username already exists")

    user = User(
        username=username,
        password_hash=hash_password(password),
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)

    return user


async def authenticate_user(
    db: AsyncSession,
    username: str,
    password: str,
) -> User | None:

    user = await get_user_by_username(
        db,
        username,
    )

    if not user:
        return None

    if not user.is_active:
        return None

    if not verify_password(
        password,
        user.password_hash,
    ):
        return None

    return user


from datetime import datetime, timedelta, timezone

from telegram_bot.models.telegram_session import TelegramSession

TELEGRAM_SESSION_DAYS = 30
async def get_telegram_session(
    db: AsyncSession,
    telegram_user_id: int,
) -> TelegramSession | None:

    result = await db.execute(
        select(TelegramSession).where(
            TelegramSession.telegram_user_id
            == telegram_user_id
        )
    )

    session = result.scalar_one_or_none()

    if not session:
        return None

    if session.expires_at < datetime.now(timezone.utc):

        await db.delete(session)
        await db.commit()

        return None

    return session


async def create_telegram_session(
    db: AsyncSession,
    telegram_user_id: int,
    user_id: int,
) -> TelegramSession:

    existing = await get_telegram_session(
        db,
        telegram_user_id,
    )

    if existing:
        existing.user_id = user_id

        existing.expires_at = (
            datetime.now(timezone.utc)
            + timedelta(days=TELEGRAM_SESSION_DAYS)
        )

        await db.commit()

        return existing

    session = TelegramSession(
        telegram_user_id=telegram_user_id,
        user_id=user_id,
        expires_at=(
            datetime.now(timezone.utc)
            + timedelta(days=TELEGRAM_SESSION_DAYS)
        ),
    )

    db.add(session)

    await db.commit()
    await db.refresh(session)

    return session


async def logout_telegram_user(
    db: AsyncSession,
    telegram_user_id: int,
) -> None:

    session = await get_telegram_session(
        db,
        telegram_user_id,
    )

    if session:
        await db.delete(session)
        await db.commit()