from sqlalchemy import select

from telegram_bot.models.agents_trace import AgentTrace
from telegram_bot.models.llm_event import LLMEvent


async def get_trace(db, user_id:int, trace_id:str):
    trace = await db.scalar(
        select(AgentTrace).where(
            AgentTrace.id == trace_id,
            AgentTrace.user_id == user_id
        )
    )

    if trace is None:
        return None
    
    events_result = await db.execute(
        select(LLMEvent)
        .where(
            LLMEvent.trace_id == trace_id,
            LLMEvent.user_id == user_id,
        )
        .order_by(LLMEvent.started_at.asc())
    )

    return trace, events_result.scalars().all()