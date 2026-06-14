from document_service import (
    save_whatsapp_document
)

from loader_service import load_documents
from chunking_service import create_chunks
from chroma_service import store_documents
from metadata_service import save_document_metadata

def ingest_document(
    sender:str,
    media_id:str,
    filename:str,
    mime_type:str
):

    # download the document and save it in a file and get its path
    filepath = save_whatsapp_document(
        media_id=media_id,
        filename=filename
    )

    # now load the documents
    documents = load_documents(filepath)

    # create chunks of the documents
    chunks = create_chunks(documents)

    for chunk in chunks:
        chunk.metadata.update(
            {
                "sender": sender,
                "filename": filename
            }
        )

    #store in vector store    
    store_documents(chunks)

    save_document_metadata(
        sender=sender,
        filename=filename,
        filepath=filepath,
        mime_type=mime_type,
        chunk_count=len(chunks)
    )

    return {
        "status": "success",
        "filename": filename,
        "chunk_count": len(chunks)
    }

