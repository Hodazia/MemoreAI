from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import (
    APIRouter, Depends, HTTPException, Query, status
)

from pydantic import BaseModel, Field
from sqlalchemy import select, func, desc, or_
from sqlalchemy.ext.asyncio import AsyncSession

from telegram_bot.api.dependencies import get_admin_user
from telegram_bot.core.database import get_db

from telegram_bot.models.document import Document
from telegram_bot.models.user import User
from telegram_bot.models.workflow import Workflow
from telegram_bot.models.conversation import Conversation
from telegram_bot.models.message import Message
from telegram_bot.models.agents_trace import AgentTrace
from telegram_bot.models.observability import ObservabilityAlert

router = APIRouter(
    prefix="/admin",
    tags=["Admin Control Plane"]
)

class UserStatusUpdate(BaseModel):
    is_active:bool


class WorkflowStatusUpdate(BaseModel):
    enabled:bool

def pagination_params(page:int, page_size:int):
    offset = (page - 1) * page_size
    return offset , page_size


def paginated_response(items, total, page, page_size):
    return {
        "items": items,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": (total + page_size - 1) // page_size,
        },
    }

@router.get("/dashboard")
async def admin_dashboard(
    db:AsyncSession = Depends(get_db),
    admin:User  = Depends(get_admin_user),
):
    now = datetime.now(timezone.utc)
    last_24_hours = now - timedelta(hours=24)

    users = await db.scalar(
        select(func.count(User.id))
    )

    active_users = await db.scalar(
        select(func.count(User.id))
        .where(User.is_active.is_(True))
    )


    conversations = await db.scalar(
        select(func.count(Conversation.id))
    )

    messages = await db.scalar(
        select(func.count(Message.id))
    )

    documents = await db.scalar(
        select(func.count(Document.id))
    )

    failed_documents = await db.scalar(
        select(func.count(Document.id))
        .where(Document.status == "failed")
    )

    workflows = await db.scalar(
        select(func.count(Workflow.id))
    )

    enabled_workflows = await db.scalar(
        select(func.count(Workflow.id))
        .where(Workflow.enabled.is_(True))
    )

    traces = await db.scalar(
        select(func.count(AgentTrace.id))
        .where(AgentTrace.started_at >= last_24_hours)
    )

    failed_traces = await db.scalar(
        select(func.count(AgentTrace.id))
        .where(
            AgentTrace.started_at >= last_24_hours,
            AgentTrace.status.in_(["failed", "error", "failure"]),
        )
    )

    return {
        "generated_at": now,
        "users": {
            "total": users or 0,
            "active": active_users or 0,
        },
        "conversations": conversations or 0,
        "messages": messages or 0,
        "documents": {
            "total": documents or 0,
            "failed": failed_documents or 0,
        },
        "workflows": {
            "total": workflows or 0,
            "enabled": enabled_workflows or 0,
        },
        "ai": {
            "traces_last_24_hours": traces or 0,
            "failed_traces_last_24_hours": failed_traces or 0,
        },
    }


@router.get("/users")
async def admin_list_users(
    search: Optional[str] = None,
    page:int = Query(1, ge=1),
    page_size: int = Query(20,ge=1,le=100),
    db:AsyncSession = Depends(get_db),
    admin:User = Depends(get_admin_user),
):
    query = select(User)

    if search:
        query = query.where(
            User.username.ilike(f"%{search}%")
        )

    
    total = await db.scalar(
        select(func.count()).select_from(query.subquery())
    )

    offset, limit = pagination_params(page, page_size)

    result = await db.execute(
        query
        .order_by(User.created_at.desc())
        .offset(offset)
        .limit(limit)
    )

    users = result.scalars().all()

    items = [
        {
            "id": user.id,
            "username": user.username,
            "is_admin": user.is_admin,
            "is_active": user.is_active,
            "created_at": user.created_at,
        }
        for user in users
    ]

    return paginated_response(
        items, total or 0, page, page_size
    )


@router.get("/users/{user_id}")
async def admin_get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    user = await db.get(User, user_id)

    if user is None:
        raise HTTPException(404, "User not found")

    conversations = await db.scalar(
        select(func.count(Conversation.id))
        .where(Conversation.user_id == user_id)
    )

    messages = await db.scalar(
        select(func.count(Message.id))
        .join(
            Conversation,
            Message.conversation_id == Conversation.id
        )
        .where(Conversation.user_id == user_id)
    )

    documents = await db.scalar(
        select(func.count(Document.id))
        .where(Document.user_id == user_id)
    )

    workflows = await db.scalar(
        select(func.count(Workflow.id))
        .where(Workflow.user_id == user_id)
    )

    return {
        "user": {
            "id": user.id,
            "username": user.username,
            "is_admin": user.is_admin,
            "is_active": user.is_active,
            "created_at": user.created_at,
        },
        "usage": {
            "conversations": conversations or 0,
            "messages": messages or 0,
            "documents": documents or 0,
            "workflows": workflows or 0,
        },
    }


@router.patch("/users/{user_id}/status")
async def admin_update_user_status(
    user_id: int,
    payload: UserStatusUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    user = await db.get(User, user_id)

    if user is None:
        raise HTTPException(404, "User not found")

    if user.id == admin.id and not payload.is_active:
        raise HTTPException(
            400,
            "You cannot deactivate your own admin account."
        )

    user.is_active = payload.is_active

    await db.commit()
    await db.refresh(user)

    return {
        "message": "User status updated",
        "user_id": user.id,
        "is_active": user.is_active,
    }

@router.get("/documents")
async def admin_list_documents(
    user_id: Optional[int] = None,
    document_status: Optional[str] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    '''
    get documents of all the users
    
    '''
    query = select(Document)

    if user_id is not None:
        query = query.where(Document.user_id == user_id)

    if document_status:
        query = query.where(Document.status == document_status)

    if search:
        query = query.where(
            Document.original_filename.ilike(f"%{search}%")
        )

    total = await db.scalar(
        select(func.count()).select_from(query.subquery())
    )

    offset, limit = pagination_params(page, page_size)

    result = await db.execute(
        query
        .order_by(Document.created_at.desc())
        .offset(offset)
        .limit(limit)
    )

    documents = result.scalars().all()

    items = [
        {
            "id": document.id,
            "user_id": document.user_id,
            "filename": document.original_filename,
            "file_type": document.file_type,
            "file_size": document.file_size,
            "status": document.status,
            "error_message": document.error_message,
            "created_at": document.created_at,
            "updated_at": document.updated_at,
        }
        for document in documents
    ]

    return paginated_response(
        items, total or 0, page, page_size
    )


@router.get("/documents/{document_id}")
async def admin_get_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    document = await db.get(Document, document_id)

    if document is None:
        raise HTTPException(404, "Document not found")

    return {
        "id": document.id,
        "user_id": document.user_id,
        "original_filename": document.original_filename,
        "file_type": document.file_type,
        "file_size": document.file_size,
        "status": document.status,
        "error_message": document.error_message,
        "created_at": document.created_at,
        "updated_at": document.updated_at,
    }


@router.get("/documents/stats")
async def admin_document_stats(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    result = await db.execute(
        select(
            Document.status,
            func.count(Document.id).label("count"),
            func.sum(Document.file_size).label("total_size"),
        )
        .group_by(Document.status)
    )

    return {
        "items": [
            {
                "status": row.status,
                "count": row.count,
                "total_size_bytes": row.total_size or 0,
            }
            for row in result.all()
        ]
    }