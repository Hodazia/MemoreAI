from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from telegram_bot.core.database import get_db
from telegram_bot.core.security import decode_token
from telegram_bot.models.user import User


security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:

    try:
        ''' 
        so the httpauthorizationcredentials will automatically lok for
        bearer token in authorization  header and it will parse header and 
        credentials will store HTTPAuthorizationCredentials object and its credentials will
        have token
        '''
        payload = decode_token(
            credentials.credentials
            # the above contains tokens,
        )

        if payload.get("type") != "access":
            raise ValueError()

        user_id = int(payload["sub"])

    except Exception:

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.is_active.is_(True),
        )
    )

    user = result.scalar_one_or_none()

    if not user:

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user


async def get_admin_user(
    current_user: User = Depends(get_current_user),
) -> User:

    if not current_user.is_admin:

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )

    return current_user