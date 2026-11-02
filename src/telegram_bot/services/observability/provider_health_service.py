from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func
from telegram_bot.models.llm_event import LLMEvent


async def get_provider_health(db, user_id: int):
    since = datetime.now(timezone.utc) - timedelta(minutes=15)

    names = await db.execute(
        select(LLMEvent.provider)
        .where(
            LLMEvent.user_id == user_id,
            LLMEvent.event_type == "llm",
            LLMEvent.started_at >= since,
        )
        .distinct()
    )

    output = {}

    for (provider,) in names.all():
        name = provider or "unknown"
        base = [
            LLMEvent.user_id == user_id,
            LLMEvent.provider == provider,
            LLMEvent.event_type == "llm",
            LLMEvent.started_at >= since,
        ]

        total = await db.scalar(
            select(func.count(LLMEvent.id)).where(*base)
        ) or 0

        failures = await db.scalar(
            select(func.count(LLMEvent.id)).where(
                *base,
                LLMEvent.status == "failed",
            )
        ) or 0

        output[name] = {
            "external_status": "unknown",
            "observed_calls": total,
            "observed_failures": failures,
        }

    return output