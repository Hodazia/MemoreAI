'''
knowledge service for RAG!





'''

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from telegram_bot.vectorstore.pinecone import get_vector_store

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=800,
    chunk_overlap=150,
)

from uuid import uuid4


async def add_user_knowledge(
    user_id: int,
    text: str,
    source: str = "manual",
):
    documents = text_splitter.create_documents(
        [text]
    )

    namespace = f"user-{user_id}"

    for document in documents:
        document.metadata.update({
            "user_id": str(user_id),
            "source": source,
        })

    ids = [
        str(uuid4())
        for _ in documents
    ]

    vector_store = get_vector_store()

    await vector_store.aadd_documents(
        documents=documents,
        ids=ids,
        namespace=namespace,
    )

    return {
        "chunks_created": len(documents),
        "namespace": namespace,
    }

async def search_user_knowledge(
    user_id: int,
    query: str,
    k: int = 4,
):
    vector_store = get_vector_store()

    namespace = f"user-{user_id}"

    results = await vector_store.asimilarity_search(
        query=query,
        k=k,
        namespace=namespace,
    )

    return results