from celery import Celery

from telegram_bot.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "telegram_bot",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["telegram_bot.tasks.workflows"],
)

celery_app.conf.update(
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "check-due-workflows-every-minute": {
            "task": "telegram_bot.tasks.workflows.dispatch_due_workflows",  # publish the dispatcher task every 60 sec
            "schedule": 60.0,
        },
    },
    task_acks_late=True, # acknowledges a task when a worker receives it, after execution instead
    task_reject_on_worker_lost=True, # reject a task if the worker process disappears unexpectedly , allowing redelivery
    worker_prefetch_multiplier=1,
)

'''
when is it scheduled?? schedule = 60 means what!!

Every 60sec , celery beat publishes a task named dispatch_due_workflows. A celery worker consumes it
and checks postgresql for workflows whose next_run_at has passed.


'''