from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Integer, String,Text, DateTime, Index, ForeignKey, JSON,Float
from sqlalchemy.orm import Mapped, mapped_column 
from telegram_bot.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)

'''
this table stores individual LLM calls, tool calls and errors. A trace can have many events
'''
class LLMEvent(Base):
    __tablename__ = "llm_events"

    id:Mapped[str] = mapped_column(
        String(36),
        primary_key = True,
        default=lambda: str(uuid4()),
    )

    trace_id: Mapped[str] = mapped_column(
        ForeignKey("agent_traces.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # llm, tool or error
    event_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False
    )

    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    provider: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    model_name: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    latency_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    input_tokens: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    output_tokens: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    estimated_cost_usd: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    error_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Small, sanitized metadata only.
    metadata_json: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    __table_args__ = (
        Index(
            "ix_llm_events_user_started",
            "user_id",
            "started_at",
        ),
        Index(
            "ix_llm_events_trace_started",
            "trace_id",
            "started_at",
        ),
        Index(
            "ix_llm_events_type_status",
            "event_type",
            "status",
        ),
    )