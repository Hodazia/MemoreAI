from sqlalchemy import select

from telegram_bot.core.config import get_settings
from telegram_bot.core.database import AsyncSessionLocal
from telegram_bot.core.security import hash_password
from telegram_bot.models.user import User



async def create_admin_if_not_exists():
    '''
    create an admin by default from the .env settings
    username and password can be saved in the env files!
    
    '''

    settings = get_settings()

    async with AsyncSessionLocal() as db:
        '''
        it automatically opens the DB connection under the variable name db,
        and guarantees that the connection is closed properly when the code block
        finishes, 
        
        '''
        result = await db.execute(
            select(User).where(
                User.username
                == settings.admin_username
            )
        )

        existing = result.scalar_one_or_none()
        if existing:
            '''
            if an admin already exists don't create a new one
            '''
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