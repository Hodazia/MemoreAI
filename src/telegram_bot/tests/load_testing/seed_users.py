
import asyncio
import bcrypt

from sqlalchemy import select
from telegram_bot.core.database import AsyncSessionLocal
from telegram_bot.models.user import User
from telegram_bot.models.conversation import Conversation
from pwdlib import PasswordHash
from .config import config

password_hash = PasswordHash.recommended()
from telegram_bot.core.security import hash_password

async def seed_users():
    created_users = []

    async with AsyncSessionLocal() as db:
        for i in range(1, config.total_users + 1):
            username = f"{config.username_prefix}_{i}"

            existing_user = await db.scalar(
                select(User).where(
                    User.username == username
                )
            )

            if existing_user:
                user = existing_user
            else:
                user = User(
                    username=username,
                    password_hash=hash_password(
                        f"LoadTestPassword_{i}_2026!"
                    ),
                    is_admin=False,
                    is_active=True,
                )

                db.add(user)
                await db.flush()

            # Give each user an independent conversation.
            conversation = Conversation(
                user_id=user.id,
                title=f"Load test conversation {config.run_id}",
            )

            db.add(conversation)

            created_users.append({
                "user_id": user.id,
                "username": username,
                "conversation": conversation,
            })

        await db.commit()

        # Flush generated IDs and return serializable records.
        result = []

        for item in created_users:
            await db.refresh(item["conversation"])

            result.append({
                "user_id": item["user_id"],
                "username": item["username"],
                "conversation_id": item["conversation"].id,
            })

        return result


if __name__ == "__main__":
    users = asyncio.run(seed_users())

    print(f"Seeded {len(users)} users.")

    for user in users[:5]:
        print(user)