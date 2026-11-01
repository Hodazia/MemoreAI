from datetime import datetime , timezone

from sqlalchemy import Boolean, DateTime, String, Integer, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column 

from telegram_bot.core.database import Base

def utc_now():
    return datetime.now(timezone.utc)

class Workflow(Base):

    __tablename__ = "workflows"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(150), nullable=False
    )
    prompt: Mapped[str] = mapped_column(
        Text, nullable=False
    )

    schedule_time: Mapped[str] = mapped_column(
        String(5), nullable=False
    )
    timezone: Mapped[str] = mapped_column(
        String(64), default="Asia/Kolkata", nullable=False
    )
    next_run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )

    telegram_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    email_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, index=True, nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )