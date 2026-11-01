
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from telegram_bot.models.memory import Memory

MAX_MEMORY_LENGTH = 500
MAX_MEMORIES_PER_USER = 100

async def create_memory(
    db:AsyncSession,
    user_id:int,
    content:str
) -> Memory:
    content = content.strip()

    if not content:
        raise ValueError("Memory cannot be empty.")

    if len(content) > MAX_MEMORY_LENGTH:
        raise ValueError(
            f"Memory cannot exceed {MAX_MEMORY_LENGTH} characters."
        )
    
    #Enforce the per-user limit in the DB layer
    count_result = await db.execute(
        select(Memory.id)
        .where(Memory.user_id == user_id)
        .limit(MAX_MEMORIES_PER_USER + 1)
    )

    existing_ids = count_result.scalars().all()
    if len(existing_ids) >= MAX_MEMORIES_PER_USER:
        raise ValueError(
            "You have reached the memory limit. "
            "Delete an existing memory before adding another."
        )

    # Avoid creating exact duplicate memories.
    result = await db.execute(
        select(Memory).where(
            Memory.user_id == user_id,
            Memory.content == content,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        return existing

    memory = Memory(
        user_id=user_id,
        content=content,
    )

    db.add(memory)
    await db.flush()

    return memory

async def list_memories(
    db: AsyncSession,
    user_id: int,
) -> list[Memory]:
    result = await db.execute(
        select(Memory)
        .where(Memory.user_id == user_id)
        .order_by(Memory.created_at.desc(), Memory.id.desc())
        .limit(MAX_MEMORIES_PER_USER)
    )

    return list(result.scalars().all())


async def get_memory(
    db: AsyncSession,
    user_id: int,
    memory_id: int,
) -> Memory | None:
    result = await db.execute(
        select(Memory).where(
            Memory.id == memory_id,
            Memory.user_id == user_id,
        )
    )

    return result.scalar_one_or_none()


async def update_memory(
    db: AsyncSession,
    user_id: int,
    memory_id: int,
    content: str,
) -> Memory | None:
    content = content.strip()

    if not content:
        raise ValueError("Memory cannot be empty.")

    if len(content) > MAX_MEMORY_LENGTH:
        raise ValueError(
            f"Memory cannot exceed {MAX_MEMORY_LENGTH} characters."
        )

    memory = await get_memory(
        db,
        user_id,
        memory_id,
    )

    if memory is None:
        return None

    memory.content = content
    await db.flush()

    return memory


async def delete_memory(
    db: AsyncSession,
    user_id: int,
    memory_id: int,
) -> bool:
    result = await db.execute(
        delete(Memory).where(
            Memory.id == memory_id,
            Memory.user_id == user_id,
        )
    )

    return result.rowcount > 0


async def delete_all_memories(
    db: AsyncSession,
    user_id: int,
) -> int:
    result = await db.execute(
        delete(Memory).where(
            Memory.user_id == user_id,
        )
    )

    return result.rowcount or 0


async def get_memories_for_agent(
    db: AsyncSession,
    user_id: int,
    limit: int = 10,
) -> list[Memory]:
    result = await db.execute(
        select(Memory)
        .where(Memory.user_id == user_id)
        .order_by(Memory.updated_at.desc(), Memory.id.desc())
        .limit(limit)
    )

    return list(result.scalars().all())


