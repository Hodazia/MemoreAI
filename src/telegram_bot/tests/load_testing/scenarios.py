import asyncio
import random
import logging

from sqlalchemy import select

from telegram_bot.core.database import AsyncSessionLocal
from telegram_bot.models.memory import Memory
from telegram_bot.models.workflow import Workflow
from telegram_bot.services.chat_service import process_user_message
from telegram_bot.tasks.workflows import next_daily_run

logger = logging.getLogger(__name__)


QUESTIONS = [
    "Explain how Redis pub/sub works.",
    "What is the difference between threads and processes?",
    "Explain database indexing with an example.",
    "How does a distributed message queue work?",
    "Explain the CAP theorem.",
    "What is connection pooling?",
    "How does a load balancer distribute traffic?",
    "Explain the difference between SQL and NoSQL.",
]


class VirtualUser:

    def __init__(
        self,
        *,
        user_id: int,
        username: str,
        conversation_id: int,
    ):
        self.user_id = user_id
        self.username = username
        self.conversation_id = conversation_id

        self.messages_sent = 0
        self.messages_received = 0
        self.scenario = None

    async def send_message(self, text: str):
        async with AsyncSessionLocal() as db:
            response = await process_user_message(
                db,
                user_id=self.user_id,
                conversation_id=self.conversation_id,
                content=text,
            )

        self.messages_sent += 1
        self.messages_received += 1

        return response

    async def chat_scenario(self):
        number_of_messages = random.randint(3, 6)

        for _ in range(number_of_messages):
            question = random.choice(QUESTIONS)

            response = await self.send_message(question)

            if not response:
                raise RuntimeError(
                    "Agent returned an empty response."
                )

            await asyncio.sleep(
                random.uniform(0.2, 1.0)
            )

    async def memory_scenario(self):
        content = (
            f"I am virtual user {self.username}. "
            "I am learning distributed systems."
        )

        async with AsyncSessionLocal() as db:
            memory = Memory(
                user_id=self.user_id,
                content=content,
            )

            db.add(memory)
            await db.commit()
            await db.refresh(memory)

            memory_id = memory.id

        # Ask the agent a question that should use memory.
        response = await self.send_message(
            "What am I learning?"
        )

        if not response:
            raise RuntimeError("Memory scenario failed.")

        return memory_id

    async def workflow_scenario(self):
        async with AsyncSessionLocal() as db:
            workflow = Workflow(
                user_id=self.user_id,
                name=f"Load test workflow {self.username}",
                prompt=(
                    "Give me a short summary of "
                    "recent AI engineering developments."
                ),
                schedule_time="23:59",
                timezone="UTC",
                next_run_at=next_daily_run(
                    "23:59",
                    "UTC",
                ),
                telegram_enabled=False,
                email_enabled=False,
                enabled=True,
            )

            db.add(workflow)
            await db.commit()
            await db.refresh(workflow)

            return workflow.id

    async def rag_scenario(self):
        """
        This tests retrieval against documents that have
        already been ingested for this user.

        Actual file upload and ingestion must be connected
        to your existing document ingestion service.
        """
        async with AsyncSessionLocal() as db:
            from telegram_bot.models.document import Document

            document = await db.scalar(
                select(Document)
                .where(
                    Document.user_id == self.user_id,
                    Document.status == "completed",
                )
                .order_by(Document.created_at.desc())
                .limit(1)
            )

        if document is None:
            logger.warning(
                "No indexed document for user %s; "
                "skipping RAG scenario.",
                self.user_id,
            )
            return

        response = await self.send_message(
            "Summarize the contents of my uploaded document."
        )

        if not response:
            raise RuntimeError("RAG scenario failed.")

    async def mixed_scenario(self):
        await self.chat_scenario()
        await self.memory_scenario()
        await self.workflow_scenario()

    async def run(self, scenario: str):
        self.scenario = scenario

        if scenario == "chat":
            await self.chat_scenario()

        elif scenario == "memory":
            await self.memory_scenario()

        elif scenario == "workflow":
            await self.workflow_scenario()

        elif scenario == "rag":
            await self.rag_scenario()

        elif scenario == "mixed":
            await self.mixed_scenario()

        else:
            raise ValueError(
                f"Unknown scenario: {scenario}"
            )