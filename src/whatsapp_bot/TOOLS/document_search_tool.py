from langchain.tools import tool
from services.chroma_service import vector_store

def create_document_search_tool(
    sender: str
):

    @tool
    def search_documents(
        query: str
    ) -> str:
        """
        Search the user's uploaded documents.
        Use this whenever the user asks
        questions about files they uploaded.
        """

        docs = vector_store.similarity_search(
            query=query,
            k=5,
            filter={
                "sender": sender
            }
        )

        if not docs:

            return (
                "No relevant document "
                "information found."
            )

        return "\n\n".join(
            [
                doc.page_content
                for doc in docs
            ]
        )

    return search_documents