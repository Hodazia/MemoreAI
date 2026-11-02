from datetime import datetime, timezone

from sqlalchemy import select

from telegram_bot.models.observability import ObservabilityAlert
from telegram_bot.services.observability.anomaly_service import (
    detect_anomalies,
)


def utc_now():
    return datetime.now(timezone.utc)

async def set_alert_rule(
    db,
    user_id: int,
    metric_name: str,
    threshold: float,
):
    allowed = {
        "error_rate",
        "p95_latency_ms",
        "daily_cost_usd",
    }

    if metric_name not in allowed:
        raise ValueError("Unsupported alert metric")

    if threshold <= 0:
        raise ValueError("Threshold must be positive")

    rule = await db.scalar(
        select(ObservabilityAlert).where(
            ObservabilityAlert.user_id == user_id,
            ObservabilityAlert.record_type == "rule",
            ObservabilityAlert.metric_name == metric_name,
        )
    )

    if rule is None:
        rule = ObservabilityAlert(
            user_id=user_id,
            record_type="rule",
            metric_name=metric_name,
            threshold=threshold,
            enabled=True,
            status="active",
        )
        db.add(rule)
    else:
        rule.threshold = threshold
        rule.enabled = True

    await db.commit()
    await db.refresh(rule)
    return rule


async def get_alert_rules(db, user_id: int):
    result = await db.execute(
        select(ObservabilityAlert).where(
            ObservabilityAlert.user_id == user_id,
            ObservabilityAlert.record_type == "rule",
        )
    )
    return result.scalars().all()


async def get_active_alerts(db, user_id: int):
    result = await db.execute(
        select(ObservabilityAlert).where(
            ObservabilityAlert.user_id == user_id,
            ObservabilityAlert.record_type == "incident",
            ObservabilityAlert.status == "active",
        ).order_by(ObservabilityAlert.created_at.desc())
    )
    return result.scalars().all()


async def evaluate_user_alerts(db, user_id: int):
    rules = await get_alert_rules(db, user_id)
    thresholds = {
        rule.metric_name: rule.threshold
        for rule in rules
        if rule.enabled
    }

    incidents = await detect_anomalies(
        db,
        user_id,
        thresholds,
    )

    active = await get_active_alerts(db, user_id)
    active_by_metric = {
        incident.metric_name: incident
        for incident in active
    }

    for incident in incidents:
        metric = incident["metric_name"]
        existing = active_by_metric.get(metric)

        if existing:
            existing.message = incident["message"]
            continue

        db.add(
            ObservabilityAlert(
                user_id=user_id,
                record_type="incident",
                metric_name=metric,
                threshold=incident["threshold"],
                status="active",
                message=incident["message"],
                fingerprint=f"{user_id}:{metric}",
            )
        )

    # Resolve incidents that are no longer breached.
    incident_metrics = {
        incident["metric_name"] for incident in incidents
    }

    for existing in active:
        if existing.metric_name not in incident_metrics:
            existing.status = "resolved"
            existing.resolved_at = utc_now()

    await db.commit()
    return await get_active_alerts(db, user_id)


'''
these functions evaluate alerts on demand, A scheduled celery task can later call
evaluate_user_alerts() for opted-in users and push Telegram notifications when new incidents appear


'''
