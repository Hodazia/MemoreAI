from telegram_bot.services.observability.metrics_service import (
    get_summary, get_latency_summary, get_cost_summary
)

async def detect_anomalies(db, user_id:int, thresholds: dict):
    incidents = []

    summary = await get_summary(db, user_id, hours=1)
    latency  = await get_latency_summary(db, user_id, hours=24)
    costs = await get_cost_summary(db, user_id, hours=24)

    error_threshold = thresholds.get("error_rate")
    latency_threshold = thresholds.get("p95_latency_ms")
    cost_threshold = thresholds.get("daily_cost_usd")

    if (
        error_threshold is not None
        and summary["total"] >= 5
        and summary["success_rate"] is not None
        and 100 - summary["success_rate"] >= error_threshold
    ):
        incidents.append({
            "metric_name": "error_rate",
            "value": round(100 - summary["success_rate"], 2),
            "threshold": error_threshold,
            "message": "The recent AI request failure rate is high.",
        })

    if (
        latency_threshold is not None
        and latency["p95_ms"] is not None
        and latency["p95_ms"] >= latency_threshold
    ):
        incidents.append({
            "metric_name": "p95_latency_ms",
            "value": latency["p95_ms"],
            "threshold": latency_threshold,
            "message": "AI request latency is above the configured limit.",
        })

    if (
        cost_threshold is not None
        and costs["estimated_cost_usd"] is not None
        and costs["estimated_cost_usd"] >= cost_threshold
    ):
        incidents.append({
            "metric_name": "daily_cost_usd",
            "value": costs["estimated_cost_usd"],
            "threshold": cost_threshold,
            "message": "Estimated AI spending has crossed its threshold.",
        })

    return incidents