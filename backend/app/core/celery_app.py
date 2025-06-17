import os
from celery import Celery
from dotenv import load_dotenv

load_dotenv()

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "tasks",
    broker=redis_url,
    backend=redis_url,
    include=["app.tasks.transcription"],
)

celery_app.conf.update(
    task_track_started=True,
    task_time_limit=1800,  # 30 minutes hard timeout
    task_soft_time_limit=1500,  # 25 minutes soft timeout
    worker_prefetch_multiplier=1,  # Process one task at a time
    broker_connection_retry_on_startup=True,
)
