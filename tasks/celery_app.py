import os
from dotenv import load_dotenv
from celery import Celery
from celery.schedules import crontab

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

app = Celery("car_price_bot", broker=REDIS_URL, backend=REDIS_URL)

app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)

app.conf.beat_schedule = {
    "scrape-daily": {
        "task": "tasks.celery_app.run_scraper",
        "schedule": crontab(hour=1, minute=0),  # every day at 01:00 UTC
    },
    "retrain-daily": {
        "task": "tasks.celery_app.train_model",
        "schedule": crontab(hour=2, minute=0),  # every day at 02:00 UTC
    },
}


@app.task(name="tasks.celery_app.train_model")
def train_model():
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from ml.train import run_training
    result = run_training()
    return result


@app.task(name="tasks.celery_app.run_scraper")
def run_scraper(pages=None):
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from scraper.run import run
    return run(n_pages=pages)
