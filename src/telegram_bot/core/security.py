from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash

from telegram_bot.core.config import get_settings


settings = get_settings()

password_hash = PasswordHash.recommended()

# hash the password
def hash_password(password: str) -> str:
    return password_hash.hash(password)

# verify the password,
def verify_password(
    password: str,
    hashed_password: str,
) -> bool:

    return password_hash.verify(
        password,
        hashed_password,
    )

# user_id -> jwt -> session_token!
def create_access_token(user_id: int) -> str:

    '''
    if we run datetime.now(timezone.utc) in our country, it will force the time to give in UTC not in IST
    Even if we deploy on AWS EC2, it will still give the same UTC time
    the below has no problem since we are calculating a duration to expire, we do not require the current time
    '''
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )

    payload = {
        "sub": str(user_id),
        "type": "access",
        "exp": expire,
    }

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def create_refresh_token(user_id: int) -> str:

    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.refresh_token_expire_days
    )

    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "exp": expire,
    }

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_token(token: str) -> dict:

    return jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )