from dataclasses import dataclass
from langchain.tools import tool, ToolRuntime
from telegram_bot.services.knowledge_service import (
    search_user_knowledge,
)

#
@dataclass
class AgentContext:
    user_id: int


def build_document_tools(user_id: int):
    @tool
    async def search_my_documents(query: str) -> str:
        """Search the authenticated user's uploaded documents
        for information relevant to a question.
        Use this when answering questions about their files.
        """
        results = await search_user_knowledge(
            user_id=user_id,
            query=query,
            k=4,
        )

        if not results:
            return "No relevant information was found in your documents."

        return "\n\n".join(
            f"Source: {doc.metadata.get('source', 'Unknown document')}\n"
            f"Content: {doc.page_content}"
            for doc in results
        )

    return [search_my_documents]
