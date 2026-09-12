from sqlalchemy import select

from telegram_bot.core.config import get_settings
from telegram_bot.core.database import AsyncSessionLocal
from telegram_bot.core.security import hash_password
from telegram_bot.models.user import User


async def create_admin_if_not_exists():

    settings = get_settings()

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User).where(
                User.username
                == settings.admin_username
            )
        )

        existing = result.scalar_one_or_none()
        if existing:
            return

        admin = User(
            username=settings.admin_username,
            password_hash=hash_password(
                settings.admin_password
            ),
            is_admin=True,
        )

        db.add(admin)

        await db.commit()