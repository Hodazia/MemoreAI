from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from telegram_bot.core.database import get_db
from telegram_bot.core.security import (
    create_access_token,
    create_refresh_token,
)
from telegram_bot.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
)
from telegram_bot.services.auth_service import (
    authenticate_user,
    register_user,
)


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.post(
    "/register",
    response_model=TokenResponse,
)
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db),
):

    try:

        user = await register_user(
            db,
            request.username,
            request.password,
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=409,
            detail=str(exc),
        )

    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post(
    "/login",
    response_model=TokenResponse,
)
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db),
):

    user = await authenticate_user(
        db,
        request.username,
        request.password,
    )

    if not user:

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )