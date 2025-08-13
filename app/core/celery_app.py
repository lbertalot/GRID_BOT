from celery import Celery
from celery.schedules import crontab
import os

# Configuración de Celery
celery_app = Celery(
    "gridbot",
    broker=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0"),
    include=[
        "app.services.trading_tasks",
        "app.services.rebalancing_tasks", 
        "app.services.ml_tasks",
        "app.services.alert_tasks"
    ]
)

# Configuración de Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=int(os.getenv("CELERY_TASK_HARD_TIMEOUT", str(30 * 60))),
    task_soft_time_limit=int(os.getenv("CELERY_TASK_SOFT_TIMEOUT", str(25 * 60))),
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    broker_connection_retry_on_startup=True,
)

# Tareas programadas
celery_app.conf.beat_schedule = {
    "trading-cycle": {
        "task": "app.services.trading_tasks.execute_trading_cycle",
        "schedule": 60.0,  # Cada minuto
    },
    "rebalance-check": {
        "task": "app.services.rebalancing_tasks.check_and_rebalance",
        "schedule": 3600.0,  # Cada hora
    },
    "performance-analysis": {
        "task": "app.services.ml_tasks.analyze_performance",
        "schedule": crontab(hour=0, minute=0),  # Diario a medianoche
    },
    "risk-assessment": {
        "task": "app.services.trading_tasks.assess_risk",
        "schedule": 300.0,  # Cada 5 minutos
    },
} 