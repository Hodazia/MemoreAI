from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Integer, String,Text, DateTime, Index, ForeignKey, Float, Boolean
from sqlalchemy.orm import Mapped, mapped_column 
from telegram_bot.core.database import Base


def utc_now() -> datetime:
    return datetime.now()

class ObservabilityAlert(Base):
    __tablename__ = "observability_alerts"

    id:Mapped[int] = mapped_column(
        Integer,
        primary_key = True,
        autoincrement= True
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )


    # rule or incident
    record_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    # error_rate, p95_latency_ms, daily_cost_usd
    metric_name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    threshold: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="active",
    )

    message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    fingerprint: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        Index(
            "ix_observability_alerts_user_type",
            "user_id",
            "record_type",
        ),
    )