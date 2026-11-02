from datetime import datetime, timedelta, timezone
from langchain_core.language_models import LLM
from sqlalchemy import select, func, case

from telegram_bot.models.agents_trace import AgentTrace
from telegram_bot.models.llm_event import LLMEvent

def utc_now():
    return datetime.now(timezone.utc)


async def get_summary(db, user_id:int, hours:int = 24):
    start = utc_now() - timedelta(hours=hours)

    result = await db.execute(
        select(
            func.count(AgentTrace.id).label("total"),
            func.sum(case(
                    (AgentTrace.status == "success", 1),
                    else_=0,
                )).label("successes"),
            func.sum(
                case(
                    (AgentTrace.status == "failed", 1),
                    else_=0,
                )
            ).label("failures"),
            func.avg(AgentTrace.latency_ms).label("avg_latency"), 
        ).where(
            AgentTrace.user_id == user_id,
            AgentTrace.started_at >= start
        )
    )


    row = result.one()
    total = row.total or 0
    successes = row.successes or 0
    failures = row.failures or 0

    return {
        "period_hours": hours,
        "total": total,
        "successes": successes,
        "failures": failures,
        "success_rate": (
            successes / total * 100 if total else None
        ),
        "avg_latency_ms": (
            float(row.avg_latency)
            if row.avg_latency is not None
            else None
        ),
    }


async def get_cost_summary(db, user_id:int, hours:int = 24):
    start = utc_now() - timedelta(hours=hours)

    result = await db.execute(
        select(
            func.sum(LLMEvent.input_tokens),
            func.sum(LLMEvent.output_tokens),
            func.sum(LLMEvent.estimated_cost_usd),
        ).where(
            LLMEvent.user_id == user_id,
            LLMEvent.event_type == "llm",
            LLMEvent.started_at >= start
        )
    )

    input_tokens, output_tokens, cost = result.one()

    return {
        "period_hours": hours,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": (
            input_tokens + output_tokens
            if input_tokens is not None and output_tokens is not None
            else None
        ),
        "estimated_cost_usd": float(cost) if cost is not None else None,
    }


async def get_model_breakdown(
    db,
    user_id: int,
    hours: int = 24,
):
    start = utc_now() - timedelta(hours=hours)

    result = await db.execute(
        select(
            LLMEvent.provider,
            LLMEvent.model_name,
            func.count(LLMEvent.id).label("calls"),
            func.sum(
                case(
                    (LLMEvent.status == "failed", 1),
                    else_=0,
                )
            ).label("failures"),
            func.avg(LLMEvent.latency_ms).label("avg_latency"),
            func.sum(LLMEvent.estimated_cost_usd).label("cost"),
        ).where(
            LLMEvent.user_id == user_id,
            LLMEvent.event_type == "llm",
            LLMEvent.started_at >= start,
        ).group_by(
            LLMEvent.provider,
            LLMEvent.model_name,
        )
    )

    return [
        {
            "provider": row.provider or "unknown",
            "model": row.model_name or "unknown",
            "calls": row.calls,
            "failures": row.failures or 0,
            "avg_latency_ms": (
                float(row.avg_latency)
                if row.avg_latency is not None else None
            ),
            "estimated_cost_usd": (
                float(row.cost) if row.cost is not None else None
            ),
        }
        for row in result
    ]


async def get_recent_failures(
    db,
    user_id: int,
    limit: int = 10,
):
    result = await db.execute(
        select(LLMEvent)
        .where(
            LLMEvent.user_id == user_id,
            LLMEvent.status == "failed",
        )
        .order_by(LLMEvent.started_at.desc())
        .limit(min(max(limit, 1), 50))
    )

    return result.scalars().all()


async def get_latency_summary(
    db,
    user_id: int,
    hours: int = 24,
):
    start = utc_now() - timedelta(hours=hours)

    result = await db.execute(
        select(AgentTrace.latency_ms)
        .where(
            AgentTrace.user_id == user_id,
            AgentTrace.started_at >= start,
            AgentTrace.latency_ms.is_not(None),
        )
        .order_by(AgentTrace.latency_ms.asc())
    )

    values = [row[0] for row in result.all()]

    if not values:
        return {
            "count": 0,
            "average_ms": None,
            "p95_ms": None,
            "slowest_ms": None,
        }

    # Nearest-rank percentile; exact for this in-memory sample.
    p95_index = max(0, int(0.95 * len(values) + 0.999999) - 1)

    return {
        "count": len(values),
        "average_ms": sum(values) / len(values),
        "p95_ms": values[p95_index],
        "slowest_ms": max(values),
    }