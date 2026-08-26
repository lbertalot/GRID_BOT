from celery import Celery
from celery.schedules import crontab
import os
import ssl

# Priorizar REDIS_URL de Heroku si está disponible, luego CELERY_BROKER_URL
redis_url = os.getenv("REDIS_URL") or os.getenv(
    "CELERY_BROKER_URL", "redis://localhost:6379/0"
)
celery_result_backend = os.getenv("REDIS_URL") or os.getenv(
    "CELERY_RESULT_BACKEND", "redis://localhost:6379/0"
)

# Configuración de Celery con soporte para SSL (rediss://)
broker_use_ssl = {}
redis_backend_use_ssl = {}

# Si usa SSL (rediss://), configurar opciones SSL
if redis_url.startswith("rediss://"):
    # Para Celery con Redis SSL, usar broker_use_ssl
    broker_use_ssl = {
        "ssl_cert_reqs": ssl.CERT_NONE,  # Heroku Redis usa SSL pero sin verificación de certificado
    }
    redis_backend_use_ssl = {
        "ssl_cert_reqs": ssl.CERT_NONE,
    }

# Configuración de Celery
celery_app = Celery(
    "gridbot",
    broker=redis_url,
    backend=celery_result_backend,
    include=[
        "app.services.trading_tasks",
        "app.services.rebalancing_tasks",
        "app.services.ml_tasks",
        "app.services.alert_tasks",
        "app.services.portfolio_snapshot_service",  # portfolio-snapshot-agent
        "app.services.pipeline_health_tasks",
        "app.services.desk_status_tasks",
    ],
)

# ✅ MEJORA 1: Configuración de Celery optimizada
# - prefetch_multiplier=1: Sin pre-fetch, mejor distribucion
# - max_tasks_per_child=1000: Reciclar workers para evitar memory leaks
# - acks_late=True: Confirmar tasks después de completarse
# - reject_on_worker_lost=True: Re-encolar si worker muere
conf_dict = {
    "task_serializer": "json",
    "accept_content": ["json"],
    "result_serializer": "json",
    "timezone": "UTC",
    "enable_utc": True,
    "task_track_started": True,
    "task_time_limit": int(os.getenv("CELERY_TASK_HARD_TIMEOUT", str(30 * 60))),
    "task_soft_time_limit": int(os.getenv("CELERY_TASK_SOFT_TIMEOUT", str(25 * 60))),
    "worker_prefetch_multiplier": int(os.getenv("CELERY_WORKER_PREFETCH_MULTIPLIER", "1")),
    "worker_max_tasks_per_child": int(os.getenv("CELERY_WORKER_MAX_TASKS_PER_CHILD", "1000")),
    "broker_connection_retry_on_startup": True,
    "task_acks_late": True,
    "task_reject_on_worker_lost": True,
    "worker_hijack_root_logger": False,
    # Eventos para Flower (/metrics). El worker también debe arrancar con -E.
    "worker_send_task_events": True,
    "task_send_sent_event": True,
}

# Añadir opciones SSL si es necesario
if broker_use_ssl:
    conf_dict["broker_use_ssl"] = broker_use_ssl
if redis_backend_use_ssl:
    conf_dict["redis_backend_use_ssl"] = redis_backend_use_ssl

celery_app.conf.update(**conf_dict)

# ✅ MEJORA 2: Tareas programadas con delays optimizados
# trading-cycle-tick: cada 60s (orquesta ciclo de 5m internamente)
# rebalance-check: cada hora (no es crítico)
# risk-assessment: cada 5 minutos
# pipeline-health: cada 15 minutos
# Tareas programadas
try:
    from app.core.celery_tracing import install_celery_tracing

    install_celery_tracing()
except Exception:
    pass

celery_app.conf.beat_schedule = {
    "trading-cycle-tick": {
        "task": "app.services.trading_tasks.trading_cycle_tick",
        "schedule": 60.0,  # Cada 60 segundos
        "options": {"queue": "celery"},
    },
    "risk-assessment": {
        "task": "app.services.trading_tasks.assess_risk",
        "schedule": 300.0,  # Cada 5 minutos
        "options": {"queue": "low"},
    },
    "rebalance-check": {
        "task": "app.services.rebalancing_tasks.check_and_rebalance",
        "schedule": 3600.0,  # Cada hora
        "options": {"queue": "low"},
    },
    "performance-analysis": {
        "task": "app.services.ml_tasks.analyze_performance",
        "schedule": crontab(hour=0, minute=0),  # Diario a medianoche
        "options": {"queue": "low"},
    },
    "dust-sweep-weekly": {
        "task": "app.services.trading_tasks.dust_sweep",
        "schedule": crontab(minute=0, hour=3, day_of_week="sun"),  # Domingos 03:00 UTC
        "options": {"queue": "low"},
        "args": (True,),  # dry_run por defecto
    },
    "portfolio-snapshot": {
        "task": "app.services.portfolio_snapshot_service.capture_portfolio_snapshot",
        "schedule": 900.0,  # 15 minutos
        "options": {"queue": "low"},
    },
    "pipeline-db-writes-health": {
        "task": "app.services.pipeline_health_tasks.check_pipeline_db_writes",
        "schedule": 900.0,  # 15 minutos
        "options": {"queue": "low"},
    },
    # Desk paper window: digest CEO + áreas → Telegram (opt-in DESK_HOURLY_STATUS_ENABLED)
    "desk-hourly-ceo-digest": {
        "task": "app.services.desk_status_tasks.send_desk_hourly_digest",
        "schedule": crontab(minute=5),  # cada hora :05 UTC
        "options": {"queue": "low"},
    },
    "desk-eod-day-plan": {
        "task": "app.services.desk_status_tasks.send_desk_eod_day_plan",
        "schedule": crontab(hour=0, minute=45),  # post-cierre 00:45 UTC
        "options": {"queue": "low"},
    },
}
