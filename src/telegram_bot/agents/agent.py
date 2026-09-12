from langchain.agents import create_agent
from langchain_openai import ChatOpenAI

from telegram_bot.agents.prompts import SYSTEM_PROMPT
from telegram_bot.core.config import get_settings


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
    tools=[],
    system_prompt=SYSTEM_PROMPT,
)

async def ask_agent(message: str) -> str:
    """
    Send a user message to the AI agent and return the final response.
    """

    result = await agent.ainvoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": message,
                }
            ]
        }
    )

    final_message = result["messages"][-1]

    return final_message.content