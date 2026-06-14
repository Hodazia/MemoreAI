from langchain_chroma import Chroma
from embedding_service import embeddings

VECTOR_DB_PATH="chroma_db"

vector_store = Chroma(
    collection_name="documents",
    embedding_function=embeddings,
    persist_directory=VECTOR_DB_PATH
)

def store_documents(
    chunks
):
    """
    Insert chunks into Chroma
    """

    vector_store.add_documents(
        chunks
    )


def get_retriever(
    k: int = 5
):
    return vector_store.as_retriever(
        search_kwargs={
            "k": k
        }
    )