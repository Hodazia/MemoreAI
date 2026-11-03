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
from telegram_bot.models.llm_event import LLMEvent
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

@router.get("/workflows")
async def admin_list_workflows(
    user_id: Optional[int] = None,
    enabled: Optional[bool] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    query = select(Workflow)

    if user_id is not None:
        query = query.where(Workflow.user_id == user_id)

    if enabled is not None:
        query = query.where(Workflow.enabled.is_(enabled))

    total = await db.scalar(
        select(func.count()).select_from(query.subquery())
    )

    offset, limit = pagination_params(page, page_size)

    result = await db.execute(
        query
        .order_by(Workflow.next_run_at.asc())
        .offset(offset)
        .limit(limit)
    )

    workflows = result.scalars().all()

    items = [
        {
            "id": workflow.id,
            "user_id": workflow.user_id,
            "name": workflow.name,
            "schedule_time": workflow.schedule_time,
            "timezone": workflow.timezone,
            "next_run_at": workflow.next_run_at,
            "telegram_enabled": workflow.telegram_enabled,
            "email_enabled": workflow.email_enabled,
            "enabled": workflow.enabled,
            "created_at": workflow.created_at,
        }
        for workflow in workflows
    ]

    return paginated_response(
        items, total or 0, page, page_size
    )


@router.get("/workflows/{workflow_id}")
async def admin_get_workflow(
    workflow_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    workflow = await db.get(Workflow, workflow_id)

    if workflow is None:
        raise HTTPException(404, "Workflow not found")

    return {
        "id": workflow.id,
        "user_id": workflow.user_id,
        "name": workflow.name,
        "prompt": workflow.prompt,
        "schedule_time": workflow.schedule_time,
        "timezone": workflow.timezone,
        "next_run_at": workflow.next_run_at,
        "telegram_enabled": workflow.telegram_enabled,
        "email_enabled": workflow.email_enabled,
        "enabled": workflow.enabled,
        "created_at": workflow.created_at,
    }


@router.patch("/workflows/{workflow_id}/status")
async def admin_update_workflow_status(
    workflow_id: int,
    payload: WorkflowStatusUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    workflow = await db.get(Workflow, workflow_id)

    if workflow is None:
        raise HTTPException(404, "Workflow not found")

    workflow.enabled = payload.enabled

    await db.commit()
    await db.refresh(workflow)

    return {
        "message": "Workflow status updated",
        "workflow_id": workflow.id,
        "enabled": workflow.enabled,
    }

@router.get("/knowledge/overview")
async def admin_knowledge_overview(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    result = await db.execute(
        select(
            Document.status,
            func.count(Document.id).label("count"),
            func.count(func.distinct(Document.user_id)).label("users"),
        )
        .group_by(Document.status)
    )

    rows = result.all()

    total_documents = sum(row.count for row in rows)

    return {
        "total_documents": total_documents,
        "indexed_documents": sum(
            row.count for row in rows
            if row.status == "indexed"
        ),
        "failed_documents": sum(
            row.count for row in rows
            if row.status == "failed"
        ),
        "processing_documents": sum(
            row.count for row in rows
            if row.status == "processing"
        ),
        "status_breakdown": [
            {
                "status": row.status,
                "documents": row.count,
                "users": row.users,
            }
            for row in rows
        ],
        "vector_database": "Pinecone",
        "note": (
            "Document counts come from SQL metadata. "
            "They are not a direct count of Pinecone vectors."
        ),
    }


@router.get("/knowledge/users/{user_id}")
async def admin_user_knowledge(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    user = await db.get(User, user_id)

    if user is None:
        raise HTTPException(404, "User not found")

    result = await db.execute(
        select(Document)
        .where(Document.user_id == user_id)
        .order_by(Document.created_at.desc())
    )

    documents = result.scalars().all()

    return {
        "user_id": user_id,
        "pinecone_namespace": f"user-{user_id}",
        "documents": [
            {
                "id": doc.id,
                "filename": doc.original_filename,
                "status": doc.status,
                "file_type": doc.file_type,
                "created_at": doc.created_at,
            }
            for doc in documents
        ],
    }

@router.get("/observability/overview")
async def admin_observability_overview(
    hours: int = Query(24, ge=1, le=720),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    trace_result = await db.execute(
        select(
            func.count(AgentTrace.id),
            func.sum(
                func.cast(
                    AgentTrace.status.in_(
                        ["failed", "error", "failure"]
                    ),
                    # Boolean cast works on PostgreSQL.
                    # See the alternative below if using another DB.
                    AgentTrace.status.type
                )
            ),
            func.avg(AgentTrace.latency_ms),
        )
        .where(AgentTrace.started_at >= since)
    )

    total_traces, failed_traces, average_latency = (
        trace_result.one()
    )

    llm_result = await db.execute(
        select(
            func.count(LLMEvent.id),
            func.sum(LLMEvent.input_tokens),
            func.sum(LLMEvent.output_tokens),
            func.sum(LLMEvent.estimated_cost_usd),
        )
        .where(
            LLMEvent.started_at >= since,
            LLMEvent.event_type == "llm",
        )
    )

    calls, input_tokens, output_tokens, total_cost = (
        llm_result.one()
    )

    return {
        "window_hours": hours,
        "generated_at": datetime.now(timezone.utc),
        "traces": {
            "total": total_traces or 0,
            "failed": failed_traces or 0,
            "error_rate_percent": (
                (failed_traces or 0) / total_traces * 100
                if total_traces else None
            ),
            "average_latency_ms": (
                float(average_latency)
                if average_latency is not None else None
            ),
        },
        "llm": {
            "calls": calls or 0,
            "input_tokens": input_tokens or 0,
            "output_tokens": output_tokens or 0,
            "estimated_cost_usd": (
                float(total_cost)
                if total_cost is not None else None
            ),
        },
        "scope": "all_users",
    }


@router.get("/observability/users/{user_id}")
async def admin_user_observability(
    user_id: int,
    hours: int = Query(24, ge=1, le=720),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    user = await db.get(User, user_id)

    if user is None:
        raise HTTPException(404, "User not found")

    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    trace_result = await db.execute(
        select(
            func.count(AgentTrace.id),
            func.avg(AgentTrace.latency_ms),
        )
        .where(
            AgentTrace.user_id == user_id,
            AgentTrace.started_at >= since,
        )
    )

    trace_count, avg_latency = trace_result.one()

    llm_result = await db.execute(
        select(
            func.count(LLMEvent.id),
            func.sum(LLMEvent.input_tokens),
            func.sum(LLMEvent.output_tokens),
            func.sum(LLMEvent.estimated_cost_usd),
        )
        .where(
            LLMEvent.user_id == user_id,
            LLMEvent.started_at >= since,
            LLMEvent.event_type == "llm",
        )
    )

    calls, input_tokens, output_tokens, cost = llm_result.one()

    return {
        "user_id": user_id,
        "window_hours": hours,
        "traces": trace_count or 0,
        "average_latency_ms": (
            float(avg_latency) if avg_latency is not None else None
        ),
        "llm": {
            "calls": calls or 0,
            "input_tokens": input_tokens or 0,
            "output_tokens": output_tokens or 0,
            "estimated_cost_usd": (
                float(cost) if cost is not None else None
            ),
        },
    }


@router.get("/observability/traces")
async def admin_list_traces(
    user_id: Optional[int] = None,
    trace_status: Optional[str] = None,
    hours: int = Query(24, ge=1, le=720),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    query = select(AgentTrace).where(
        AgentTrace.started_at >= since
    )

    if user_id is not None:
        query = query.where(AgentTrace.user_id == user_id)

    if trace_status:
        query = query.where(AgentTrace.status == trace_status)

    total = await db.scalar(
        select(func.count()).select_from(query.subquery())
    )

    offset, limit = pagination_params(page, page_size)

    result = await db.execute(
        query
        .order_by(AgentTrace.started_at.desc())
        .offset(offset)
        .limit(limit)
    )

    items = [
        {
            "id": str(trace.id),
            "user_id": trace.user_id,
            "status": trace.status,
            "started_at": trace.started_at,
            "finished_at": trace.finished_at,
            "latency_ms": trace.latency_ms,
            "event_count": trace.event_count,
            "error_type": trace.error_type,
            "error_message": trace.error_message,
        }
        for trace in result.scalars().all()
    ]

    return paginated_response(
        items, total or 0, page, page_size
    )


@router.get("/observability/failures")
async def admin_observability_failures(
    hours: int = Query(24, ge=1, le=720),
    user_id: Optional[int] = None,
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    query = select(AgentTrace).where(
        AgentTrace.started_at >= since,
        AgentTrace.status.in_(["failed", "error", "failure"]),
    )

    if user_id is not None:
        query = query.where(AgentTrace.user_id == user_id)

    result = await db.execute(
        query
        .order_by(AgentTrace.started_at.desc())
        .limit(limit)
    )

    return {
        "items": [
            {
                "trace_id": str(trace.id),
                "user_id": trace.user_id,
                "status": trace.status,
                "started_at": trace.started_at,
                "latency_ms": trace.latency_ms,
                "error_type": trace.error_type,
                "error_message": trace.error_message,
            }
            for trace in result.scalars().all()
        ]
    }

@router.get("/observability/models")
async def admin_model_breakdown(
    hours: int = Query(24, ge=1, le=720),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    result = await db.execute(
        select(
            LLMEvent.provider,
            LLMEvent.model_name,
            func.count(LLMEvent.id).label("calls"),
            func.sum(LLMEvent.input_tokens).label("input_tokens"),
            func.sum(LLMEvent.output_tokens).label("output_tokens"),
            func.sum(LLMEvent.estimated_cost_usd).label("cost"),
        )
        .where(
            LLMEvent.started_at >= since,
            LLMEvent.event_type == "llm",
        )
        .group_by(
            LLMEvent.provider,
            LLMEvent.model_name,
        )
        .order_by(func.count(LLMEvent.id).desc())
    )

    return {
        "window_hours": hours,
        "items": [
            {
                "provider": row.provider,
                "model": row.model_name,
                "calls": row.calls,
                "input_tokens": row.input_tokens or 0,
                "output_tokens": row.output_tokens or 0,
                "estimated_cost_usd": (
                    float(row.cost) if row.cost is not None else None
                ),
            }
            for row in result.all()
        ],
    }


@router.get("/observability/alerts")
async def admin_list_alerts(
    alert_status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    query = select(ObservabilityAlert)

    if alert_status:
        query = query.where(
            ObservabilityAlert.status == alert_status
        )

    result = await db.execute(
        query.order_by(ObservabilityAlert.created_at.desc())
        .limit(100)
    )

    return {
        "items": [
            {
                "id": alert.id,
                "user_id": alert.user_id,
                "record_type": alert.record_type,
                "metric_name": alert.metric_name,
                "threshold": alert.threshold,
                "enabled": alert.enabled,
                "status": alert.status,
                "message": alert.message,
                "created_at": alert.created_at,
            }
            for alert in result.scalars().all()
        ]
    }