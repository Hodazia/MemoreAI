# vectorstore/pinecone.py

from functools import lru_cache

from pinecone import Pinecone
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore

from telegram_bot.core.config import get_settings


settings = get_settings()


@lru_cache
def get_embeddings():
    return OpenAIEmbeddings(
        model=settings.embedding_model,
        api_key=settings.openai_api_key,
    )


@lru_cache
def get_pinecone_client():
    return Pinecone(
        api_key=settings.pinecone_api_key,
    )


@lru_cache
def get_pinecone_index():
    client = get_pinecone_client()

    return client.Index(
        settings.pinecone_index_name
    )


@lru_cache
def get_vector_store():
    return PineconeVectorStore(
        index=get_pinecone_index(),
        embedding=get_embeddings(),
    )