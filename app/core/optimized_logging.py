# Configuración principal de logging optimizada
# En producción (ENVIRONMENT=production o LOG_LEVEL=WARNING) solo se emite WARNING+
# a consola para mantener volumen bajo (~10 MB/día Papertrail free).
import logging.config
import os


def _effective_log_level() -> str:
    """Nivel para root/console: WARNING en producción para limitar volumen (Papertrail 10 MB/día)."""
    env = os.getenv("ENVIRONMENT", "production").lower()
    level_name = os.getenv("LOG_LEVEL", "WARNING" if env == "production" else "INFO").upper()
    return level_name if level_name in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL") else "WARNING"


def _build_logging_config() -> dict:
    root_level = _effective_log_level()
    # Consola siempre WARNING+ en producción para no exceder 10 MB/día en Papertrail
    console_level = "WARNING" if os.getenv("ENVIRONMENT", "production").lower() == "production" else root_level
    if console_level not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
        console_level = "WARNING"

    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "detailed": {
                "format": "%(asctime)s | %(name)s | %(levelname)s | %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "simple": {
                "format": "%(asctime)s | %(levelname)s | %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": console_level,
                "formatter": "detailed",
                "stream": "ext://sys.stdout",
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": root_level,
                "formatter": "detailed",
                "filename": os.getenv("LOG_FILE_PATH", "logs/trading.log"),
                "maxBytes": 10485760,
                "backupCount": 5,
            },
            "error_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "ERROR",
                "formatter": "detailed",
                "filename": os.path.join(
                    os.path.dirname(os.getenv("LOG_FILE_PATH", "logs/trading.log") or "logs"),
                    "errors.log",
                ),
                "maxBytes": 10485760,
                "backupCount": 3,
            },
        },
        "loggers": {
            "sqlalchemy.engine": {"level": "WARNING", "handlers": ["console"], "propagate": False},
            "sqlalchemy.pool": {"level": "WARNING", "handlers": ["console"], "propagate": False},
            "sqlalchemy.dialects": {"level": "WARNING", "handlers": ["console"], "propagate": False},
            "trading_system": {
                "level": root_level,
                "handlers": ["console", "file"],
                "propagate": False,
            },
            "app.services.binance_client_singleton": {
                "level": "WARNING",
                "handlers": ["file", "error_file"],
                "propagate": False,
            },
            "app.core.metrics_manager": {
                "level": root_level,
                "handlers": ["console"],
                "propagate": False,
            },
        },
        "root": {"level": root_level, "handlers": ["console", "file"]},
    }


def setup_optimized_logging():
    """Configura el sistema de logging optimizado. Respeta ENVIRONMENT y LOG_LEVEL."""
    log_dir = os.path.dirname(os.getenv("LOG_FILE_PATH", "logs/trading.log") or "logs")
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
    config = _build_logging_config()
    # En Heroku/producción sin LOG_FILE_PATH: solo consola (stdout → Papertrail), sin archivo efímero
    env = os.getenv("ENVIRONMENT", "production").lower()
    if env == "production" and not os.getenv("LOG_FILE_PATH"):
        config["root"]["handlers"] = ["console"]
        for name in ("trading_system", "app.core.metrics_manager"):
            if name in config["loggers"] and "file" in config["loggers"][name].get("handlers", []):
                config["loggers"][name]["handlers"] = [
                    h for h in config["loggers"][name]["handlers"] if h != "file"
                ]
    logging.config.dictConfig(config)
    
    # Configurar filtros adicionales
    from app.services.symbol_error_filter import filter_symbol_errors
    from app.core.sqlalchemy_config import SlowQueryFilter
    
    # Aplicar filtros
    binance_logger = logging.getLogger('app.services.binance_client_singleton')
    filter_symbol_errors(binance_logger)
    
    sqlalchemy_logger = logging.getLogger('sqlalchemy.engine')
    sqlalchemy_logger.addFilter(SlowQueryFilter(threshold_ms=100))
    
    logger = logging.getLogger(__name__)
    logger.info("✅ Sistema de logging optimizado configurado")
    
    return logger
