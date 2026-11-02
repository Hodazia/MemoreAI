from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Integer, String,Text, DateTime, Index, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column 
from telegram_bot.core.database import Base


def utc_now() -> datetime:
    return datetime.now()

class AgentTrace(Base):
    __tablename__ = "agent_traces"
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default = lambda: str(uuid4)
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="running"
    )

    started_at:Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now
    )

    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    latency_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    event_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )