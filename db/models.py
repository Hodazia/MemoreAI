from sqlalchemy.orm import declarative_base,Mapped,mapped_column
from sqlalchemy import DateTime

from datetime import datetime, timezone

Base = declarative_base()

'''
Define a document table which stores , 
Id, sender,filename, filepath, mime_type,chunk_count, uploaded_at

'''
class Document(Base):
    __tablename__ = "documents"  

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )

    # Mapped[str] automatically implies nullable=False
    sender: Mapped[str] = mapped_column()

    filename: Mapped[str] = mapped_column()

    filepath: Mapped[str] = mapped_column()

    mime_type: Mapped[str] = mapped_column()

    # Mapped[int] implies nullable=False by default
    chunk_count: Mapped[int] = mapped_column(
        default=0
    )

    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc)  
    )