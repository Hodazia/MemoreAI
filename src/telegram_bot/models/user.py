from datetime import datetime 

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column 

from telegram_bot.core.database import Base

class User(Base):

    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False,index=True)
    password_hash:Mapped[str] = mapped_column(String(255), nullable=False)
    is_admin:Mapped[bool] = mapped_column(Boolean, default=False,nullable=False)
    is_active:Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at:Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow,
    nullable=False )
