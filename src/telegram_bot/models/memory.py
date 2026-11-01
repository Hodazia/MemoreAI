
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Index, DateTime ,Text, func
from sqlalchemy.orm import Mapped, mapped_column 
from telegram_bot.core.database import Base


class Memory(Base):
    __tablename__ = "memories"

    id : Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_memories_user_created", "user_id", "created_at"),
    )
