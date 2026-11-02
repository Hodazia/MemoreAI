import json

from langchain_openai import ChatOpenAI
from telegram_bot.core.config import get_settings
from telegram_bot.services.observability.metrics_service import (
    get_summary,
    get_cost_summary,
    get_latency_summary,
    get_model_breakdown
)

settings = get_settings()

async def generate_daily_reports(db, user_id:int) -> str:
    '''
    
    the LLM receives already-computed statistics and asks llm for a concise explaination!
    it doesn't give the model access to DB queries or privileaged tools
    
    '''
    summary = await get_summary(db, user_id, hours=24)
    costs = await get_cost_summary(db, user_id, hours=24)
    latency = await get_latency_summary(db, user_id, hours=24)
    models = await get_model_breakdown(db, user_id, hours=24)

    evidence = {
        "summary": summary,
        "costs": costs,
        "latency": latency,
        "models": models,
    }

    llm = ChatOpenAI(
        model=settings.model_name,
        temperature=settings.model_temperature,
        max_tokens=settings.model_max_tokens,
        timeout=settings.model_timeout,
        api_key=settings.openai_api_key,
    )

    prompt = f"""
    You are an AI application observability analyst.

    Generate a concise daily report for a Telegram message.

    Use only the supplied JSON evidence. Do not invent metrics,
    causes, outages, trends, savings, or comparisons.

    Explain:
    1. Overall request health.
    2. Latency and cost, if known.
    3. Any actionable issue supported by the data.
    4. If there is insufficient traffic to draw conclusions, say so.

    Unknown or null metrics must be described as unavailable.
    Return plain text, with short headings and bullet points.
    Do not return HTML tags, markdown tables, or code fences.

    DATA:
    {json.dumps(evidence, default=str)}
    """

    response = await llm.ainvoke(prompt)
    return str(response.content)
