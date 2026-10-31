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
    document_id:int | None = None,
):
    chunks = text_splitter.create_documents(
        [text]
    )

    namespace = f"user-{user_id}"

    for chunk in chunks:
        chunk.metadata.update({
            "user_id": str(user_id),
            "source": source,
        })

        if document_id is not None:
            chunk.metadata["document_id"] = str(document_id)

    vector_ids = [str(uuid4()) for _ in chunks]

    vector_store = get_vector_store()

    await vector_store.aadd_documents(
        documents=chunks,
        ids=vector_ids,
        namespace=namespace,
    )

    return {
        "chunks_created": len(chunks),
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