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


# agent = create_agent(
#     model=llm,
#     tools=[build_document_tools],
#     context_schema=AgentContext,
#     system_prompt=SYSTEM_PROMPT,
# )

async def ask_agent(messages: list[tuple[str, str]],user_id: int) -> str:
    """
    Send a user message to the AI agent and return the final response.
    the agent accepts system, user assistant , 

    Each message is a (role,content) tuple
    """
    # 1. Generate the tools list for this specific user
    user_tools = build_document_tools(user_id=user_id)

    # 2. Instantiate the agent dynamically with the active user's tools
    dynamic_agent = create_agent(
        model=llm,
        tools=user_tools,          # Passed the resolved list of tools, not the factory function
        context_schema=AgentContext,
        system_prompt=SYSTEM_PROMPT,
    )


    result = await dynamic_agent.ainvoke(
        {
            "messages": messages,
        },
        context=AgentContext(user_id=user_id)
    )

    final_message = result["messages"][-1]

     # Normal text responses from the agent are strings.
    if isinstance(final_message.content, str):
        return final_message.content

    # Handle structured/multimodal content defensively.
    return str(final_message.content)