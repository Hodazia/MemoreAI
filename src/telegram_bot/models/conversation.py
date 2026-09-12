from datetime import datetime 

from sqlalchemy import Boolean, DateTime, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column , relationship

from telegram_bot.core.database import Base

class Conversation(Base):

    __tablename__ = "conversations"

    id:Mapped[int] = mapped_column(primary_key=True,index=True)
    user_id:Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), 
    nullable=False, index=True)
    # on delete make changes to the users table also
    title:Mapped[str] = mapped_column(String(200),nullable=True)
    created_at:Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False
    )
    updated_at:Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )
    user = relationship(
        "User", backref="conversations"
    )
