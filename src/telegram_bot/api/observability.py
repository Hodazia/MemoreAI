import math
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func 
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime,time, timedelta, timezone
from typing import Optional
from pydantic import BaseModel, Field

from telegram_bot.schemas.observability import AlertRuleUpdate, AlertRuleCreate
from telegram_bot.api.dependencies import get_current_user
from telegram_bot.core.database import get_db
from telegram_bot.models.llm_event import LLMEvent
from telegram_bot.models.agents_trace import AgentTrace
from telegram_bot.models.observability import ObservabilityAlert


router = APIRouter(
    prefix="/api/v1/observability",
    tags=["AI Observability"],
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_day_start() -> datetime:
    return datetime.combine(
        utc_now().date(),
        time.min,
        tzinfo=timezone.utc,
    )


def serialize_trace(trace: AgentTrace) -> dict:
    return {
        "id": str(trace.id),
        "status": trace.status,
        "started_at": trace.started_at,
        "finished_at": trace.finished_at,
        "latency_ms": trace.latency_ms,
        "event_count": trace.event_count,
        "error_type": trace.error_type,
        "error_message": trace.error_message,
    }


def serialize_alert(alert: ObservabilityAlert) -> dict:
    return {
        "id": alert.id,
        "record_type": alert.record_type,
        "metric_name": alert.metric_name,
        "threshold": alert.threshold,
        "enabled": alert.enabled,
        "status": alert.status,
        "message": alert.message,
        "created_at": alert.created_at,
        "updated_at": alert.updated_at,
    }


async def load_summary(
    db: AsyncSession,
    user_id: int,
    since: Optional[datetime] = None,
) -> dict:
    query = select(AgentTrace).where(
        AgentTrace.user_id == user_id
    )

    if since is not None:
        query = query.where(AgentTrace.started_at >= since)

    result = await db.execute(query)
    traces = result.scalars().all()

    total = len(traces)
    failed = sum(
        1
        for trace in traces
        if str(trace.status).lower() in {"failed", "error", "failure"}
    )
    successful = sum(
        1
        for trace in traces
        if str(trace.status).lower()
        in {"success", "succeeded", "completed"}
    )

    latencies = sorted(
        float(trace.latency_ms)
        for trace in traces
        if trace.latency_ms is not None and float(trace.latency_ms) >= 0
    )

    p95_latency = None
    if latencies:
        p95_index = max(0, math.ceil(0.95 * len(latencies)) - 1)
        p95_latency = latencies[p95_index]

    return {
        "total": total,
        "successful": successful,
        "failed": failed,
        "error_rate_percent": failed / total * 100 if total else None,
        "average_latency_ms": (
            sum(latencies) / len(latencies) if latencies else None
        ),
        "p95_latency_ms": p95_latency,
    }


async def load_cost_summary(
    db: AsyncSession,
    user_id: int,
    since: Optional[datetime] = None,
) -> dict:
    query = select(
        func.count(LLMEvent.id),
        func.count(LLMEvent.estimated_cost_usd),
        func.sum(LLMEvent.estimated_cost_usd),
        func.sum(LLMEvent.input_tokens),
        func.sum(LLMEvent.output_tokens),
    ).where(
        LLMEvent.user_id == user_id,
        LLMEvent.event_type == "llm",
    )

    if since is not None:
        query = query.where(LLMEvent.started_at >= since)

    result = await db.execute(query)
    count, cost_count, total_cost, input_tokens, output_tokens = result.one()

    return {
        "llm_events": count or 0,
        "events_with_known_cost": cost_count or 0,
        "estimated_cost_usd": (
            float(total_cost) if total_cost is not None else None
        ),
        "input_tokens": (
            int(input_tokens) if input_tokens is not None else None
        ),
        "output_tokens": (
            int(output_tokens) if output_tokens is not None else None
        ),
        "currency": "USD",
    }


def require_user_id(current_user) -> int:
    user_id = getattr(current_user, "id", None)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user has no application user ID.",
        )
    return int(user_id)


# ------------------------------------------------------------
# Health and metrics
# ------------------------------------------------------------

@router.get("/health")
async def observability_health(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    user_id = require_user_id(current_user)
    since = utc_now() - timedelta(hours=24)

    summary = await load_summary(db, user_id, since)
    costs = await load_cost_summary(db, user_id, utc_day_start())

    if summary["total"] == 0:
        health_status = "no_recent_data"
    elif (
        summary["error_rate_percent"] is not None
        and summary["error_rate_percent"] >= 20
    ):
        health_status = "elevated_error_rate"
    elif (
        summary["p95_latency_ms"] is not None
        and summary["p95_latency_ms"] >= 10000
    ):
        health_status = "high_latency"
    else:
        health_status = "ok"

    return {
        "status": health_status,
        "window_hours": 24,
        "metrics": summary,
        "today_cost": costs,
        "note": (
            "Application telemetry only; this is not a direct provider "
            "health check."
        ),
    }


@router.get("/metrics")
async def observability_metrics(
    hours: int = Query(default=24, ge=1, le=720),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    user_id = require_user_id(current_user)
    since = utc_now() - timedelta(hours=hours)

    return {
        "window_hours": hours,
        "generated_at": utc_now(),
        "metrics": await load_summary(db, user_id, since),
    }


@router.get("/costs")
async def observability_costs(
    period: str = Query(default="today", pattern=r"^(today|all)$"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    user_id = require_user_id(current_user)
    since = utc_day_start() if period == "today" else None

    return {
        "period": period,
        "generated_at": utc_now(),
        "costs": await load_cost_summary(db, user_id, since),
    }


@router.get("/models")
async def observability_models(
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    user_id = require_user_id(current_user)

    result = await db.execute(
        select(
            LLMEvent.provider,
            LLMEvent.model_name,
            func.count(LLMEvent.id).label("calls"),
            func.sum(LLMEvent.input_tokens).label("input_tokens"),
            func.sum(LLMEvent.output_tokens).label("output_tokens"),
            func.sum(LLMEvent.estimated_cost_usd).label("estimated_cost_usd"),
        )
        .where(
            LLMEvent.user_id == user_id,
            LLMEvent.event_type == "llm",
        )
        .group_by(LLMEvent.provider, LLMEvent.model_name)
        .order_by(func.count(LLMEvent.id).desc())
        .limit(limit)
    )

    rows = result.all()

    return {
        "items": [
            {
                "provider": row.provider,
                "model_name": row.model_name,
                "calls": row.calls,
                "input_tokens": row.input_tokens,
                "output_tokens": row.output_tokens,
                "estimated_cost_usd": (
                    float(row.estimated_cost_usd)
                    if row.estimated_cost_usd is not None
                    else None
                ),
            }
            for row in rows
        ]
    }


# ------------------------------------------------------------
# Failed traces
# ------------------------------------------------------------

@router.get("/failures")
async def observability_failures(
    limit: int = Query(default=20, ge=1, le=100),
    hours: int = Query(default=168, ge=1, le=720),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    user_id = require_user_id(current_user)
    since = utc_now() - timedelta(hours=hours)

    result = await db.execute(
        select(AgentTrace)
        .where(
            AgentTrace.user_id == user_id,
            AgentTrace.started_at >= since,
            AgentTrace.status.in_(["failed", "error", "failure"]),
        )
        .order_by(AgentTrace.started_at.desc())
        .limit(limit)
    )

    return {
        "window_hours": hours,
        "items": [
            serialize_trace(trace)
            for trace in result.scalars().all()
        ],
    }


# ------------------------------------------------------------
# Trace details
# ------------------------------------------------------------

@router.get("/traces/{trace_id}")
async def observability_trace(
    trace_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    user_id = require_user_id(current_user)

    result = await db.execute(
        select(AgentTrace).where(
            AgentTrace.id == trace_id,
            AgentTrace.user_id == user_id,
        )
    )
    trace = result.scalar_one_or_none()

    if trace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trace not found.",
        )

    event_result = await db.execute(
        select(LLMEvent)
        .where(
            LLMEvent.trace_id == trace_id,
            LLMEvent.user_id == user_id,
        )
        .order_by(LLMEvent.started_at.asc())
        .limit(200)
    )

    events = event_result.scalars().all()

    return {
        "trace": serialize_trace(trace),
        "events": [
            {
                "id": str(event.id),
                "event_type": event.event_type,
                "name": event.name,
                "provider": event.provider,
                "model_name": event.model_name,
                "status": event.status,
                "started_at": event.started_at,
                "finished_at": event.finished_at,
                "latency_ms": event.latency_ms,
                "input_tokens": event.input_tokens,
                "output_tokens": event.output_tokens,
                "estimated_cost_usd": (
                    float(event.estimated_cost_usd)
                    if event.estimated_cost_usd is not None
                    else None
                ),
                "error_type": event.error_type,
                "error_message": event.error_message,
            }
            for event in events
        ],
    }


# ------------------------------------------------------------
# Alert rules and incidents
# ------------------------------------------------------------

@router.get("/alerts")
async def list_observability_alerts(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    user_id = require_user_id(current_user)

    result = await db.execute(
        select(ObservabilityAlert)
        .where(ObservabilityAlert.user_id == user_id)
        .order_by(ObservabilityAlert.created_at.desc())
        .limit(100)
    )

    return {
        "items": [
            serialize_alert(alert)
            for alert in result.scalars().all()
        ]
    }


@router.post(
    "/alerts",
    status_code=status.HTTP_201_CREATED,
)
async def create_observability_alert(
    payload: AlertRuleCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    user_id = require_user_id(current_user)

    result = await db.execute(
        select(ObservabilityAlert).where(
            ObservabilityAlert.user_id == user_id,
            ObservabilityAlert.record_type == "rule",
            ObservabilityAlert.metric_name == payload.metric_name,
        )
    )
    existing = result.scalar_one_or_none()

    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "An alert rule for this metric already exists. "
                "Update the existing rule instead."
            ),
        )

    rule = ObservabilityAlert(
        user_id=user_id,
        record_type="rule",
        metric_name=payload.metric_name,
        threshold=payload.threshold,
        enabled=payload.enabled,
        status="active" if payload.enabled else "disabled",
        message=f"Alert rule for {payload.metric_name}",
    )

    db.add(rule)
    await db.commit()
    await db.refresh(rule)

    return serialize_alert(rule)


@router.patch("/alerts/{alert_id}")
async def update_observability_alert(
    alert_id: int,
    payload: AlertRuleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    user_id = require_user_id(current_user)

    result = await db.execute(
        select(ObservabilityAlert).where(
            ObservabilityAlert.id == alert_id,
            ObservabilityAlert.user_id == user_id,
            ObservabilityAlert.record_type == "rule",
        )
    )
    rule = result.scalar_one_or_none()

    if rule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert rule not found.",
        )

    changes = payload.model_dump(exclude_unset=True)

    if not changes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide threshold and/or enabled.",
        )

    if "threshold" in changes and changes["threshold"] is not None:
        rule.threshold = changes["threshold"]

    if "enabled" in changes and changes["enabled"] is not None:
        rule.enabled = changes["enabled"]
        rule.status = "active" if rule.enabled else "disabled"

    await db.commit()
    await db.refresh(rule)

    return serialize_alert(rule)
