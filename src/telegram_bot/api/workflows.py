from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from telegram_bot.api.dependencies import get_current_user
from telegram_bot.core.database import get_db
from telegram_bot.models.user import User
from telegram_bot.models.workflow import Workflow
from telegram_bot.schemas.workflow import WorkflowCreateRequest,WorkflowResponse
from telegram_bot.tasks.workflows import next_daily_run

router = APIRouter(prefix="/workflows", tags=["Workflows"])

@router.post("", response_model=WorkflowResponse, status_code=201)
async def create_workflow(
    request:WorkflowCreateRequest,
    current_user:User = Depends(get_current_user),
    db:AsyncSession = Depends(get_db)
): 
    if not request.telegram_enabled and not request.email_enabled:
        raise HTTPException(
            status_code=400,
            detail="Enable at least one delivery channel"
        )

    if request.email_enabled and not getattr(current_user,"email",None):
        raise HTTPException(
            status_code=400,
            detail="Add an email address to your account first.",
        )

    workflow = Workflow(
        user_id=current_user.id,
        name=request.name,
        prompt=request.prompt,
        schedule_time=request.schedule_time,
        timezone=request.timezone,
        next_run_at=next_daily_run(
            request.schedule_time,
            request.timezone,
        ),
        telegram_enabled=request.telegram_enabled,
        email_enabled=request.email_enabled,
        enabled=True,
    )

    db.add(workflow)
    await db.commit()
    await db.refresh(workflow)

    return workflow


@router.get("", response_model=list[WorkflowResponse])
async def list_workflows(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Workflow)
        .where(Workflow.user_id == current_user.id)
        .order_by(Workflow.id.desc())
    )
    return result.scalars().all()