from sqlalchemy import select

from telegram_bot.models.document import Document

async def get_latest_documents(
    db,
    user_id:int,
    limit:int = 5
):
    result = await db.execute(
        select(Document)
        .where(
            Document.user_id == user_id,
            Document.status == "indexed"
        )
        .order_by(Document.created_at.desc())
        .limit(limit)
    )

    return result.scalars().all()