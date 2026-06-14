from db.database import SessionLocal
from db.models import Document

def save_document_metadata(
    sender:str,
    filename:str,
    filepath:str,
    mime_type:str,
    chunk_count:int 
):
    db = SessionLocal()

    try:

        document = Document(
            sender=sender,
            filename=filename,
            filepath=filepath,
            mime_type=mime_type,
            chunk_count=chunk_count
        )

        db.add(document)

        db.commit()

        db.refresh(document)

        return document

    finally:

        db.close()


def get_user_documents(
    sender: str
):

    db = SessionLocal()

    try:

        return (
            db.query(Document)
            .filter(
                Document.sender == sender
            )
            .all()
        )

    finally:

        db.close()