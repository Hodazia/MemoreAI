'''
what is this?
Telegram ID
      │
      ▼
TelegramSession
      │
      ▼
Application User

'''


from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
)
from sqlalchemy.orm import Mapped, mapped_column

from telegram_bot.core.database import Base


class TelegramSession(Base):

    __tablename__ = "telegram_sessions"

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    telegram_user_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
        nullable=False,
        index=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )