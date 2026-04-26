# Configuración optimizada para SQLAlchemy
import logging

# Reducir logs de SQLAlchemy a solo errores y warnings
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.dialects").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.orm").setLevel(logging.WARNING)


# Solo loggear consultas lentas (>100ms)
class SlowQueryFilter(logging.Filter):
    def __init__(self, threshold_ms=100):
        super().__init__()
        self.threshold_ms = threshold_ms

    def filter(self, record):
        if hasattr(record, "duration_ms"):
            return record.duration_ms > self.threshold_ms
        return False


# Aplicar filtro a SQLAlchemy
slow_query_filter = SlowQueryFilter(threshold_ms=100)
logging.getLogger("sqlalchemy.engine").addFilter(slow_query_filter)
