
import logging
import math
from datetime import datetime, time, timedelta, timezone
from html import escape
from statistics import quantiles
from typing import Optional

from sqlalchemy import func, select
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from telegram_bot.core.database import AsyncSessionLocal
from telegram_bot.models.agents_trace import AgentTrace
from telegram_bot.models.llm_event import LLMEvent
from telegram_bot.models.observability import ObservabilityAlert
from telegram_bot.tg.handlers import get_logged_in_user

logger = logging.getLogger(__name__)

# Process-local preferences only. These are not durable and do not start
# a background monitoring worker.
_monitor_enabled: set[int] = set()

VALID_RULES = {
    "error_rate": {
        "description": "Failed agent traces, percentage",
        "default_threshold": 10.0,
    },
    "p95_latency_ms": {
        "description": "95th-percentile latency, milliseconds",
        "default_threshold": 10000.0,
    },
    "daily_cost_usd": {
        "description": "Estimated LLM cost per UTC day, USD",
        "default_threshold": 5.0,
    },
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _format_duration(ms: Optional[float]) -> str:
    if ms is None:
        return "N/A"
    if ms < 1000:
        return f"{ms:.0f} ms"
    return f"{ms / 1000:.2f} s"


def _format_usd(amount: Optional[float]) -> str:
    if amount is None:
        return "Unavailable"
    return f"${amount:.6f}" if amount < 0.01 else f"${amount:.4f}"


def _format_percent(value: Optional[float]) -> str:
    return "N/A" if value is None else f"{value:.2f}%"


def _safe(value: object, limit: int = 300) -> str:
    """Escape untrusted values before including them in Telegram HTML."""
    text = str(value) if value is not None else "N/A"
    return escape(text[:limit])


async def _require_user(
    update: Update,
) -> Optional[int]:
    """Resolve Telegram ID to the application's authenticated user ID."""
    if update.effective_user is None:
        return None

    user_id = await get_logged_in_user(update.effective_user.id)
    if user_id is None and update.effective_message is not None:
        await update.effective_message.reply_text(
            "🔐 Please /login before using observability commands."
        )
    return user_id


async def _send(
    update: Update,
    text: str,
) -> None:
    message = update.effective_message
    if message is not None:
        await message.reply_text(
            text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )


async def _load_summary(db, user_id: int, since: Optional[datetime] = None):
    trace_query = select(AgentTrace).where(AgentTrace.user_id == user_id)
    if since is not None:
        trace_query = trace_query.where(AgentTrace.started_at >= since)

    traces = list((await db.execute(trace_query)).scalars().all())

    total = len(traces)
    failed = sum(1 for trace in traces if str(trace.status).lower() in {
        "failed", "error", "failure"
    })
    successful = sum(
        1 for trace in traces
        if str(trace.status).lower() in {"success", "succeeded", "completed"}
    )

    latencies = sorted(
        float(trace.latency_ms)
        for trace in traces
        if trace.latency_ms is not None and float(trace.latency_ms) >= 0
    )

    error_rate = (failed / total * 100) if total else None
    avg_latency = sum(latencies) / len(latencies) if latencies else None
    p95_latency = None

    if latencies:
        # Nearest-rank p95, deterministic and dependency-free.
        p95_index = max(0, math.ceil(0.95 * len(latencies)) - 1)
        p95_latency = latencies[p95_index]

    return {
        "total": total,
        "successful": successful,
        "failed": failed,
        "error_rate": error_rate,
        "avg_latency_ms": avg_latency,
        "p95_latency_ms": p95_latency,
    }


async def _load_costs(
    db,
    user_id: int,
    since: Optional[datetime] = None,
):
    query = select(LLMEvent).where(
        LLMEvent.user_id == user_id,
        LLMEvent.event_type == "llm",
    )
    if since is not None:
        query = query.where(LLMEvent.started_at >= since)

    events = list((await db.execute(query)).scalars().all())

    costs = [
        float(event.estimated_cost_usd)
        for event in events
        if event.estimated_cost_usd is not None
    ]
    input_tokens = [
        int(event.input_tokens)
        for event in events
        if event.input_tokens is not None
    ]
    output_tokens = [
        int(event.output_tokens)
        for event in events
        if event.output_tokens is not None
    ]

    return {
        "events": events,
        "known_cost": sum(costs) if costs else None,
        "cost_events": len(costs),
        "input_tokens": sum(input_tokens) if input_tokens else None,
        "output_tokens": sum(output_tokens) if output_tokens else None,
    }


def _utc_day_start() -> datetime:
    now = _utc_now()
    return datetime.combine(now.date(), time.min, tzinfo=timezone.utc)


async def ai_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = await _require_user(update)
    if user_id is None:
        return

    await _send(
        update,
        "<b>📊 AI Observability Commands</b>\n\n"
        "<code>/ai_health</code> — Health overview\n"
        "<code>/ai_stats</code> — Request and error statistics\n"
        "<code>/ai_cost</code> — Recorded LLM costs\n"
        "<code>/ai_cost today</code> — Today's UTC costs\n"
        "<code>/ai_failures</code> — Recent failed traces\n"
        "<code>/ai_latency</code> — Average and p95 latency\n"
        "<code>/ai_models</code> — Usage by model\n"
        "<code>/ai_trace TRACE_ID</code> — Inspect one trace\n"
        "<code>/ai_alerts</code> — View your alert rules/incidents\n"
        "<code>/ai_alerts set error_rate 10</code>\n"
        "<code>/ai_alerts set p95_latency_ms 10000</code>\n"
        "<code>/ai_alerts set daily_cost_usd 5</code>\n"
        "<code>/ai_monitor on|off</code> — Set this process's monitor preference\n"
        "<code>/ai_report daily</code> — Daily evidence-based summary\n\n"
        "<i>Costs are estimates when token usage and model pricing are available. "
        "All daily windows use UTC.</i>",
    )


async def ai_health(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = await _require_user(update)
    if user_id is None:
        return

    async with AsyncSessionLocal() as db:
        summary = await _load_summary(db, user_id, _utc_now() - timedelta(hours=24))
        costs = await _load_costs(db, user_id, _utc_day_start())

    if summary["total"] == 0:
        status = "🟡 No agent traces recorded in the last 24 hours"
    elif summary["error_rate"] is not None and summary["error_rate"] >= 20:
        status = "🔴 Elevated failure rate"
    elif (
        summary["p95_latency_ms"] is not None
        and summary["p95_latency_ms"] >= 10000
    ):
        status = "🟠 High p95 latency"
    else:
        status = "🟢 No threshold breach detected by this overview"

    await _send(
        update,
        "<b>🩺 AI Health — Last 24 Hours</b>\n\n"
        f"{status}\n\n"
        f"Requests: <b>{summary['total']}</b>\n"
        f"Successful: <b>{summary['successful']}</b>\n"
        f"Failed: <b>{summary['failed']}</b>\n"
        f"Error rate: <b>{_format_percent(summary['error_rate'])}</b>\n"
        f"Average latency: <b>{_format_duration(summary['avg_latency_ms'])}</b>\n"
        f"P95 latency: <b>{_format_duration(summary['p95_latency_ms'])}</b>\n"
        f"Today's known cost: <b>{_format_usd(costs['known_cost'])}</b>\n\n"
        "<i>This reflects recorded application activity, not a live provider "
        "health check.</i>",
    )


async def ai_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = await _require_user(update)
    if user_id is None:
        return

    async with AsyncSessionLocal() as db:
        summary = await _load_summary(db, user_id)

    await _send(
        update,
        "<b>📈 AI Request Statistics</b>\n\n"
        f"Total traces: <b>{summary['total']}</b>\n"
        f"Successful: <b>{summary['successful']}</b>\n"
        f"Failed: <b>{summary['failed']}</b>\n"
        f"Error rate: <b>{_format_percent(summary['error_rate'])}</b>\n"
        f"Average latency: <b>{_format_duration(summary['avg_latency_ms'])}</b>\n"
        f"P95 latency: <b>{_format_duration(summary['p95_latency_ms'])}</b>",
    )


async def ai_cost(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = await _require_user(update)
    if user_id is None:
        return

    args = context.args or []
    today_only = bool(args and args[0].lower() == "today")
    since = _utc_day_start() if today_only else None

    async with AsyncSessionLocal() as db:
        costs = await _load_costs(db, user_id, since)

    heading = "Today's UTC Cost" if today_only else "Recorded LLM Cost"
    cost = costs["known_cost"]
    cost_note = (
        f"${cost:.6f}" if cost is not None and cost < 0.01
        else f"${cost:.4f}" if cost is not None
        else "Unavailable — no known cost records"
    )

    await _send(
        update,
        f"<b>💰 {heading}</b>\n\n"
        f"Known estimated cost: <b>{cost_note}</b>\n"
        f"LLM events: <b>{len(costs['events'])}</b>\n"
        f"Events with cost data: <b>{costs['cost_events']}</b>\n"
        f"Input tokens recorded: <b>{costs['input_tokens'] if costs['input_tokens'] is not None else 'N/A'}</b>\n"
        f"Output tokens recorded: <b>{costs['output_tokens'] if costs['output_tokens'] is not None else 'N/A'}</b>\n\n"
        "<i>Unknown model pricing or missing token usage is not treated as $0.</i>",
    )


async def ai_failures(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = await _require_user(update)
    if user_id is None:
        return

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(AgentTrace)
            .where(
                AgentTrace.user_id == user_id,
                AgentTrace.status.in_(["failed", "error", "failure"]),
            )
            .order_by(AgentTrace.started_at.desc())
            .limit(10)
        )
        traces = result.scalars().all()

    if not traces:
        await _send(update, "<b>✅ No failed traces found.</b>")
        return

    lines = ["<b>❌ Recent Failures</b>\n"]
    for trace in traces:
        lines.append(
            f"• <code>{_safe(trace.id, 80)}</code>\n"
            f"  Started: {_safe(trace.started_at)}\n"
            f"  Error: {_safe(trace.error_type or trace.error_message or 'Unknown', 180)}\n"
        )

    lines.append("\nUse <code>/ai_trace TRACE_ID</code> for details.")
    await _send(update, "\n".join(lines))


async def ai_latency(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = await _require_user(update)
    if user_id is None:
        return

    async with AsyncSessionLocal() as db:
        summary = await _load_summary(db, user_id)

    await _send(
        update,
        "<b>⏱ AI Latency</b>\n\n"
        f"Traces with latency: <b>{'Yes' if summary['avg_latency_ms'] is not None else 'No'}</b>\n"
        f"Average: <b>{_format_duration(summary['avg_latency_ms'])}</b>\n"
        f"P95: <b>{_format_duration(summary['p95_latency_ms'])}</b>\n\n"
        "<i>P95 uses the nearest-rank method over recorded trace latencies.</i>",
    )


async def ai_models(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = await _require_user(update)
    if user_id is None:
        return

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(
                LLMEvent.provider,
                LLMEvent.model_name,
                func.count(LLMEvent.id),
                func.sum(LLMEvent.input_tokens),
                func.sum(LLMEvent.output_tokens),
                func.sum(LLMEvent.estimated_cost_usd),
            )
            .where(
                LLMEvent.user_id == user_id,
                LLMEvent.event_type == "llm",
            )
            .group_by(LLMEvent.provider, LLMEvent.model_name)
            .order_by(func.count(LLMEvent.id).desc())
            .limit(15)
        )
        rows = result.all()

    if not rows:
        await _send(update, "<b>🤖 No model usage has been recorded yet.</b>")
        return

    lines = ["<b>🤖 Model Usage</b>\n"]
    for provider, model, count, input_tokens, output_tokens, cost in rows:
        lines.append(
            f"<b>{_safe(model or 'Unknown model', 100)}</b>\n"
            f"Provider: {_safe(provider or 'Unknown', 80)}\n"
            f"Calls: {count}\n"
            f"Input tokens: {input_tokens if input_tokens is not None else 'N/A'}\n"
            f"Output tokens: {output_tokens if output_tokens is not None else 'N/A'}\n"
            f"Known cost: {_format_usd(float(cost)) if cost is not None else 'Unavailable'}\n"
        )

    await _send(update, "\n".join(lines))


async def ai_trace(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = await _require_user(update)
    if user_id is None:
        return

    if not context.args:
        await _send(update, "Usage: <code>/ai_trace TRACE_ID</code>")
        return

    trace_id = context.args[0].strip()

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(AgentTrace).where(
                AgentTrace.id == trace_id,
                AgentTrace.user_id == user_id,
            )
        )
        trace = result.scalar_one_or_none()

        if trace is None:
            await _send(update, "Trace not found.")
            return

        event_result = await db.execute(
            select(LLMEvent)
            .where(
                LLMEvent.trace_id == trace_id,
                LLMEvent.user_id == user_id,
            )
            .order_by(LLMEvent.started_at.asc())
            .limit(30)
        )
        events = event_result.scalars().all()

    lines = [
        "<b>🔎 Trace Details</b>",
        f"ID: <code>{_safe(trace.id, 100)}</code>",
        f"Status: <b>{_safe(trace.status)}</b>",
        f"Started: {_safe(trace.started_at)}",
        f"Finished: {_safe(trace.finished_at)}",
        f"Latency: {_format_duration(trace.latency_ms)}",
        f"Events: {trace.event_count if trace.event_count is not None else len(events)}",
        f"Error type: {_safe(trace.error_type)}",
        f"Error: {_safe(trace.error_message)}",
        "",
        "<b>Events</b>",
    ]

    if not events:
        lines.append("No child events recorded.")
    else:
        for event in events:
            lines.append(
                f"• <b>{_safe(event.event_type)}: {_safe(event.name, 100)}</b>\n"
                f"  Status: {_safe(event.status)} | "
                f"Latency: {_format_duration(event.latency_ms)}\n"
                f"  Model: {_safe(event.model_name, 100)}\n"
                f"  Cost: {_format_usd(event.estimated_cost_usd)}"
            )

    await _send(update, "\n".join(lines))


async def ai_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = await _require_user(update)
    if user_id is None:
        return

    args = context.args or []

    # /ai_alerts set <metric_name> <threshold>
    if args and args[0].lower() == "set":
        if len(args) != 3:
            await _send(
                update,
                "Usage:\n"
                "<code>/ai_alerts set error_rate 10</code>\n"
                "<code>/ai_alerts set p95_latency_ms 10000</code>\n"
                "<code>/ai_alerts set daily_cost_usd 5</code>",
            )
            return

        metric_name = args[1].lower()
        if metric_name not in VALID_RULES:
            await _send(
                update,
                "Unknown metric. Allowed: <code>error_rate</code>, "
                "<code>p95_latency_ms</code>, <code>daily_cost_usd</code>.",
            )
            return

        try:
            threshold = float(args[2])
            if not math.isfinite(threshold) or threshold <= 0:
                raise ValueError
        except ValueError:
            await _send(update, "Threshold must be a positive number.")
            return

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(ObservabilityAlert).where(
                    ObservabilityAlert.user_id == user_id,
                    ObservabilityAlert.record_type == "rule",
                    ObservabilityAlert.metric_name == metric_name,
                )
            )
            rule = result.scalar_one_or_none()

            if rule is None:
                rule = ObservabilityAlert(
                    user_id=user_id,
                    record_type="rule",
                    metric_name=metric_name,
                    threshold=threshold,
                    enabled=True,
                    status="active",
                    message=VALID_RULES[metric_name]["description"],
                )
                db.add(rule)
            else:
                rule.threshold = threshold
                rule.enabled = True
                rule.status = "active"

            await db.commit()

        await _send(
            update,
            f"✅ Alert rule saved.\n\n"
            f"Metric: <code>{_safe(metric_name)}</code>\n"
            f"Threshold: <b>{threshold:g}</b>\n"
            f"Enabled: <b>Yes</b>\n\n"
            "<i>A scheduled worker must evaluate rules and create incidents.</i>",
        )
        return

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ObservabilityAlert)
            .where(
                ObservabilityAlert.user_id == user_id,
                ObservabilityAlert.record_type.in_(["rule", "incident"]),
            )
            .order_by(ObservabilityAlert.created_at.desc())
            .limit(30)
        )
        alerts = result.scalars().all()

    if not alerts:
        await _send(
            update,
            "<b>🔔 No alert rules or incidents yet.</b>\n\n"
            "Create a rule with <code>/ai_alerts set error_rate 10</code>.",
        )
        return

    lines = ["<b>🔔 Your Alert Rules and Incidents</b>\n"]
    for alert in alerts:
        if alert.record_type == "rule":
            lines.append(
                f"• <b>Rule: {_safe(alert.metric_name)}</b>\n"
                f"  Threshold: {_safe(alert.threshold)}\n"
                f"  Enabled: {'Yes' if alert.enabled else 'No'}\n"
            )
        else:
            lines.append(
                f"• <b>Incident: {_safe(alert.metric_name)}</b>\n"
                f"  Status: {_safe(alert.status)}\n"
                f"  Details: {_safe(alert.message, 200)}\n"
            )

    await _send(update, "\n".join(lines))


async def ai_monitor(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = await _require_user(update)
    if user_id is None:
        return

    args = context.args or []
    if len(args) != 1 or args[0].lower() not in {"on", "off"}:
        await _send(update, "Usage: <code>/ai_monitor on</code> or <code>/ai_monitor off</code>")
        return

    if args[0].lower() == "on":
        _monitor_enabled.add(user_id)
        message = (
            "🟢 Monitor preference enabled for this bot process.\n\n"
            "This does not start a background worker or guarantee alerts."
        )
    else:
        _monitor_enabled.discard(user_id)
        message = (
            "⚪ Monitor preference disabled for this bot process.\n\n"
            "This does not delete your saved alert rules."
        )

    await _send(update, message)


async def ai_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = await _require_user(update)
    if user_id is None:
        return

    args = context.args or []
    if not args or args[0].lower() != "daily":
        await _send(update, "Usage: <code>/ai_report daily</code>")
        return

    async with AsyncSessionLocal() as db:
        summary = await _load_summary(db, user_id, _utc_day_start())
        costs = await _load_costs(db, user_id, _utc_day_start())

    # Keep this report deterministic: no extra LLM call is needed to calculate
    # metrics. A later report_service can add a narrative if desired.
    report = (
        "<b>🗓 Daily AI Report — UTC</b>\n\n"
        f"Requests: <b>{summary['total']}</b>\n"
        f"Successful: <b>{summary['successful']}</b>\n"
        f"Failed: <b>{summary['failed']}</b>\n"
        f"Error rate: <b>{_format_percent(summary['error_rate'])}</b>\n"
        f"Average latency: <b>{_format_duration(summary['avg_latency_ms'])}</b>\n"
        f"P95 latency: <b>{_format_duration(summary['p95_latency_ms'])}</b>\n"
        f"Known estimated LLM cost: <b>{_format_usd(costs['known_cost'])}</b>\n\n"
        "<i>Only persisted telemetry is included. Unknown costs are not counted as zero.</i>"
    )
    await _send(update, report)
