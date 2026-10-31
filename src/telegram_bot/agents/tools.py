from dataclasses import dataclass
from langchain.tools import tool, ToolRuntime
from telegram_bot.services.knowledge_service import (
    search_user_knowledge,
)

#
@dataclass
class AgentContext:
    user_id: int

@tool
async def search_knowledge(
    query: str,
    runtime: ToolRuntime[AgentContext],
) -> str:
    """
    Search the authenticated user's private knowledge base.

    Use this tool when the user asks about information
    that may exist in their uploaded or stored knowledge.
    """

    # the authenticated application automatically injects user_id
    user_id = runtime.context.user_id

    documents = await search_user_knowledge(
        user_id=user_id,
        query=query,
        k=4,
    )

    if not documents:
        return "No relevant information was found."

    results = []

    for document in documents:
        results.append(
            f"Source: {document.metadata.get('source', 'unknown')}\n"
            f"Content: {document.page_content}"
        )

    return "\n\n---\n\n".join(results)