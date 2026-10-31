import asyncio
from pathlib import Path

from langchain_community.document_loaders import (
    PyPDFLoader,
    Docx2txtLoader,
    TextLoader
)

from telegram_bot.models.document import Document
from telegram_bot.services.knowledge_service import add_user_knowledge

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".text"}

async def extract_text(file_path:str) -> str:
    path = Path(file_path)
    extension = path.suffix.lower()

    if(extension == ".pdf"):
        loader = PyPDFLoader(str(path))
    elif extension == ".docx":
        loader = Docx2txtLoader(str(path))
    elif extension == ".txt":
        loader = TextLoader(
            str(path),
            encoding="utf-8",
        )
    else:
        raise ValueError("Only PDF, DOCX, and TXT files are supported.")

    pages = await asyncio.to_thread(loader.load)

    text = "\n\n".join(
        page.page_content for page in pages
    ).strip()

    if not text:
        raise ValueError(
            "No readable text was found in this document."
        )

    return text


async def index_document(
    db,
    document:Document,
    user_id:int
):

    document.status = "processing"
    document.error_message = None
    await db.commit()

    try:
        text = await extract_text(document.file_path)
        result = await add_user_knowledge(
            user_id = user_id,
            text=text,
            source=document.original_filename,
            document_id=document.id
        )
        document.status = "indexed"
        await db.commit()

        return {
            "document_id": document.id,
            "chunks_created": result["chunks_created"],
            "status": document.status,
        }

    except Exception as exc:
        document.status = "failed"
        document.error_message = str(exc)[:2000]
        await db.commit()
        raise



'''

How the ingestion works
1. extract_text() selects a loader based on the extension.
2. The extracted text is split into overlapping chunks of 800 characters.
3. LangChain generates embeddings using your existing get_embeddings() configuration.
4. Pinecone stores the vectors in the user's namespace.
5. PostgreSQL records that indexing succeeded or failed.



'''
