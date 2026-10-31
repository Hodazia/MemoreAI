from langchain.agents import create_agent
from langchain_openai import ChatOpenAI

from telegram_bot.agents.prompts import SYSTEM_PROMPT
from telegram_bot.core.config import get_settings
from telegram_bot.agents.tools import (
    AgentContext,
    build_document_tools
)


settings = get_settings()


llm = ChatOpenAI(
    model=settings.model_name,
    temperature=settings.model_temperature,
    max_tokens=settings.model_max_tokens,
    timeout=settings.model_timeout,
    api_key=settings.openai_api_key,
)


agent = create_agent(
    model=llm,
    tools=[build_document_tools],
    context_schema=AgentContext,
    system_prompt=SYSTEM_PROMPT,
)

async def ask_agent(message: str,user_id: int) -> str:
    """
    Send a user message to the AI agent and return the final response.
    the agent accepts system, user assistant , 
    """

    result = await agent.ainvoke(
        {
            "messages": message,
        },
        context=AgentContext(user_id=user_id)
    )

    final_message = result["messages"][-1]

    return final_message.content