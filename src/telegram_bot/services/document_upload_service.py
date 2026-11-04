import logging
from pathlib import Path
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from telegram_bot.models.document import Document
from telegram_bot.services.document_service import (
    SUPPORTED_EXTENSIONS,
    index_document,
)

logger = logging.getLogger(__name__)

UPLOAD_DIR = Path("uploads")
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


async def save_and_index_document(
    db: AsyncSession,
    *,
    user_id: int,
    original_filename: str,
    file_size: int,
    downloaded_path: str,
):
    extension = Path(original_filename).suffix.lower()  # e.g. .pdf, .docx 

    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError("Supported formats: PDF, DOCX, TXT.")

    if file_size > MAX_FILE_SIZE:
        raise ValueError("The maximum supported file size is 10 MB.")

    stored_filename = f"{uuid4().hex}{extension}" # the new filename to be stored in /uploads/stored_filename
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    final_path = UPLOAD_DIR / stored_filename
    Path(downloaded_path).replace(final_path)

    document = Document(
        user_id=user_id,
        original_filename=Path(original_filename).name[:255],
        stored_filename=stored_filename,
        file_path=str(final_path.resolve()),
        file_type=extension.lstrip("."),
        file_size=file_size,
        status="uploaded",
    )

    try:
        db.add(document)
        await db.commit()
        await db.refresh(document)

        result = await index_document(
            db,
            document,
            user_id,
        )

        return document, result

    except Exception:
        await db.rollback()
        logger.exception(
            "Document ingestion failed for user_id=%s",
            user_id,
        )
        raise

'''

This creates a unique stored filename rather than trusting the user's filename 
for a filesystem path. The original filename is retained for display.


'''
