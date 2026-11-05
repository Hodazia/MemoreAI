import asyncio
import json
import logging
import random
import time

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from telegram_bot.tests.load_testing.config import config
from telegram_bot.tests.load_testing.seed_users import seed_users
from telegram_bot.tests.load_testing.scenarios import VirtualUser

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

logger = logging.getLogger(__name__)




SCENARIOS = [
    ("chat", config.chat_weight),
    ("memory", config.memory_weight),
    ("rag", config.rag_weight),
    ("workflow", config.workflow_weight),
    ("mixed", config.mixed_weight),
]


def choose_scenario():
    names = [item[0] for item in SCENARIOS]
    weights = [item[1] for item in SCENARIOS]

    return random.choices(
        names,
        weights=weights,
        k=1,
    )[0]


def percentile(values, p):
    if not values:
        return None

    values = sorted(values)
    index = round((p / 100) * (len(values) - 1))

    return values[index]


async def run_load_test():
    logger.info("Starting load test: %s", config.run_id)

    seeded_users = await seed_users()

    semaphore = asyncio.Semaphore(config.concurrency)

    results = {
        "run_id": config.run_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "total_users": len(seeded_users),
        "successful_users": 0,
        "failed_users": 0,
        "scenario_counts": Counter(),
        "errors": [],
        "user_latencies": [],
        "messages_sent": 0,
        "messages_received": 0,
    }

    async def execute_user(user_data):
        async with semaphore:
            user = VirtualUser(
                user_id=user_data["user_id"],
                username=user_data["username"],
                conversation_id=user_data["conversation_id"],
            )

            scenario = choose_scenario()
            started = time.perf_counter()

            results["scenario_counts"][scenario] += 1

            try:
                await user.run(scenario)

                results["successful_users"] += 1

            except Exception as exc:
                results["failed_users"] += 1

                results["errors"].append({
                    "user_id": user.user_id,
                    "scenario": scenario,
                    "error": str(exc),
                })

                logger.exception(
                    "Virtual user failed: user_id=%s scenario=%s",
                    user.user_id,
                    scenario,
                )

            finally:
                elapsed = time.perf_counter() - started

                results["user_latencies"].append(elapsed)
                results["messages_sent"] += user.messages_sent
                results["messages_received"] += user.messages_received

    started = time.perf_counter()

    await asyncio.gather(
        *[
            execute_user(user)
            for user in seeded_users
        ]
    )

    total_duration = time.perf_counter() - started

    results["finished_at"] = datetime.now(
        timezone.utc
    ).isoformat()

    results["duration_seconds"] = round(
        total_duration,
        3,
    )

    latencies = results["user_latencies"]

    report = {
        "run_id": results["run_id"],
        "total_users": results["total_users"],
        "successful_users": results["successful_users"],
        "failed_users": results["failed_users"],
        "success_rate_percent": round(
            results["successful_users"]
            / max(results["total_users"], 1)
            * 100,
            2,
        ),
        "duration_seconds": results["duration_seconds"],
        "users_per_second": round(
            results["total_users"]
            / max(total_duration, 0.001),
            2,
        ),
        "messages_sent": results["messages_sent"],
        "messages_received": results["messages_received"],
        "scenario_counts": dict(results["scenario_counts"]),
        "user_latency_seconds": {
            "p50": percentile(latencies, 50),
            "p95": percentile(latencies, 95),
            "p99": percentile(latencies, 99),
            "max": max(latencies) if latencies else None,
        },
        "errors": results["errors"],
    }

    report_dir = Path("tests/load_testing/reports")
    report_dir.mkdir(parents=True, exist_ok=True)

    report_path = report_dir / f"{config.run_id}.json"

    report_path.write_text(
        json.dumps(report, indent=4),
        encoding="utf-8",
    )

    print("\n========== LOAD TEST REPORT ==========")
    print(json.dumps(report, indent=4))
    print(f"\nReport saved to: {report_path}")


if __name__ == "__main__":
    asyncio.run(run_load_test())