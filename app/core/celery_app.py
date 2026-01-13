from celery import Celery
from celery.schedules import crontab
import os
import ssl

# Priorizar REDIS_URL de Heroku si está disponible, luego CELERY_BROKER_URL
redis_url = os.getenv("REDIS_URL") or os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
celery_result_backend = os.getenv("REDIS_URL") or os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

# Configuración de Celery con soporte para SSL (rediss://)
broker_transport_options = {}
result_backend_transport_options = {}

# Si usa SSL (rediss://), configurar opciones SSL
if redis_url.startswith("rediss://"):
    broker_transport_options = {
        'ssl_cert_reqs': ssl.CERT_NONE,  # Heroku Redis usa SSL pero sin verificación de certificado
        'ssl_ca_certs': None,
        'ssl_certfile': None,
        'ssl_keyfile': None,
    }
    result_backend_transport_options = broker_transport_options.copy()

# Configuración de Celery
celery_app = Celery(
    "gridbot",
    broker=redis_url,
    backend=celery_result_backend,
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
    broker_transport_options=broker_transport_options,
    result_backend_transport_options=result_backend_transport_options,
)

# Tareas programadas
celery_app.conf.beat_schedule = {
    "trading-cycle-tick": {
        "task": "app.services.trading_tasks.trading_cycle_tick",
        "schedule": 60.0,  # Tick cada minuto (orquesta 5m)
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
    "dust-sweep-weekly": {
        "task": "app.services.trading_tasks.dust_sweep",
        "schedule": crontab(minute=0, hour=3, day_of_week='sun'),  # Domingos 03:00 UTC
        "options": {"queue": "low"},
        "args": (True,),  # dry_run por defecto
    },
} 