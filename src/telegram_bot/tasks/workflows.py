import asyncio
import logging

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from celery import shared_task
from sqlalchemy import select

from telegram_bot.core.database import AsyncSessionLocal
from telegram_bot.models.workflow import Workflow
from telegram_bot.models.workflow_runs import WorkflowRun
from telegram_bot.agents.agent import ask_agent
from telegram_bot.models.user import User
from telegram_bot.models.telegram_session import TelegramSession
from telegram_bot.services.notification_service import ( send_email_report, send_telegram_report )
from telegram_bot.services.latest_document import get_latest_documents
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def next_daily_run(schedule_time: str, timezone_name: str):
    tz = ZoneInfo(timezone_name)
    hour, minute = map(int, schedule_time.split(":"))

    now_local = datetime.now(tz)
    candidate = now_local.replace(
        hour=hour,
        minute=minute,
        second=0,
        microsecond=0,
    )

    if candidate <= now_local:
        candidate += timedelta(days=1)

    return candidate.astimezone(timezone.utc)


async def dispatch_due():
    now = datetime.now(timezone.utc)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Workflow)
            .where(
                Workflow.enabled.is_(True),
                Workflow.next_run_at <= now,
            )
            .with_for_update(skip_locked=True)
        )
        workflows = result.scalars().all()

        jobs = []

        for workflow in workflows:
            scheduled_for = workflow.next_run_at

            run = WorkflowRun(
                workflow_id=workflow.id,
                status="queued",
            )
            db.add(run)

            workflow.next_run_at = next_daily_run(
                workflow.schedule_time,
                workflow.timezone,
            )

            jobs.append((workflow.id, run))

        await db.commit()

        # Publish only after the DB transaction commits.
        for workflow_id, run in jobs:
            await db.refresh(run)
            execute_workflow.delay(workflow_id, run.id)


@shared_task(name="telegram_bot.tasks.workflows.dispatch_due_workflows")
def dispatch_due_workflows():
    '''
    discovers due workflows and queues each runs
    '''
    asyncio.run(dispatch_due())


@shared_task(
    bind=True,
    name="telegram_bot.tasks.workflows.execute_workflow",
    max_retries=3,
    default_retry_delay=30,
)
def execute_workflow(self, workflow_id: int, run_id: int):
    '''
    performs the actual work and retries failures,
    
    '''
    try:
        asyncio.run(execute_workflow_async(workflow_id, run_id))
    except Exception as exc:
        logger.exception(
            "Workflow execution failed: workflow_id=%s run_id=%s",
            workflow_id,
            run_id,
        )
        raise self.retry(exc=exc)

async def execute_workflow_async(
    workflow_id:int, run_id:int
):
    async with AsyncSessionLocal() as db:
        workflow = await db.get(Workflow, workflow_id)
        run = await db.get(WorkflowRun, run_id)

        if not workflow or not run:
            return 

        if not workflow.enabled:
            run.status = "cancelled"  # a user might disable a workflow after the dispatcher has queued it but before the worker starts executing it
            await db.commit()
            return

        run.status = "running"
        run.started_at = datetime.now(timezone.utc)
        await db.commit()

        # Keep these values before making external calls.
        user_id = workflow.user_id
        prompt = workflow.prompt
        workflow_name = workflow.name
        telegram_enabled = workflow.telegram_enabled
        email_enabled = workflow.email_enabled

        user = await db.get(User, user_id)

        if not user:
            run.status = "failed"
            run.error_message = "Workflow owner not found."
            run.finished_at = datetime.now(timezone.utc)
            await db.commit()
            return

        email_address = getattr(user, "email", None)

        session_result = await db.execute(
            select(TelegramSession)
            .where(TelegramSession.user_id == user_id)
            .limit(1)
        )
        telegram_session = session_result.scalar_one_or_none()

        telegram_chat_id = (
            getattr(telegram_session, "telegram_user_id", None)
            if telegram_session else None
        )

        # Do not let the model choose the recipient.
        # Recipients come from trusted account/session records.
        await db.commit()

        # fetch the user's documents for context enrichment for LLM
        latest_documents = await get_latest_documents(
        db=db,
        user_id=user_id,
        limit=5,
    )

        document_context = "\n".join(
            f"- Document ID: {doc.id}; "
            f"Name: {doc.original_filename}; "
            f"Uploaded: {doc.created_at.isoformat()}"
            for doc in latest_documents
        )

    try:
        report = await ask_agent(
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Workflow: {workflow_name}\n"
                        f"Instructions: {prompt}\n\n"
                        "The following are the user's five most "
                        "recently uploaded, successfully indexed documents:\n"
                        f"{document_context}\n\n"
                        "Use the document search tool to retrieve "
                        "relevant content from these documents. "
                        "Do not assume filenames alone contain their contents."
                    ),
                }
            ],
            user_id=user_id,
        )

        if telegram_enabled:
            if not telegram_chat_id:
                raise ValueError(
                    "No linked Telegram session was found."
                )

            await send_telegram_report(
                telegram_chat_id,
                report,
            )

        if email_enabled:
            if not email_address:
                raise ValueError(
                    "The account has no email address configured."
                )

            await send_email_report(
                recipient=email_address,
                subject=f"Scheduled report: {workflow_name}",
                body=report,
            )

        async with AsyncSessionLocal() as db:
            run = await db.get(WorkflowRun, run_id)
            if run:
                run.status = "success"
                run.report = report
                run.finished_at = datetime.now(timezone.utc)
                await db.commit()

    except Exception as exc:
        async with AsyncSessionLocal() as db:
            run = await db.get(WorkflowRun, run_id)
            if run:
                run.status = "failed"
                run.error_message = str(exc)[:2000]
                run.finished_at = datetime.now(timezone.utc)
                await db.commit()
        raise

'''

the report is generated using your existing ask_agent() and user_id, so your document retrieval tool can remain
user scoped,

Telegram and email recipients come from stored account/session data, not from the AI's output.


'''