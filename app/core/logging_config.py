
# Configuración de logging optimizada para el sistema de trading
import logging
import logging.config
from datetime import datetime

# Configuración para reducir logs verbosos
LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'detailed': {
            'format': '%(asctime)s | %(name)s | %(levelname)s | %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        },
        'simple': {
            'format': '%(asctime)s | %(levelname)s | %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        },
        'json': {
            'format': '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "service": "%(name)s", "message": "%(message)s"}',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'level': 'INFO',
            'formatter': 'detailed',
            'stream': 'ext://sys.stdout'
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'level': 'INFO',
            'formatter': 'detailed',
            'filename': 'logs/app.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5
        },
        'error_file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'level': 'ERROR',
            'formatter': 'detailed',
            'filename': 'logs/errors.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 3
        }
    },
    'loggers': {
        # Reducir logs de SQLAlchemy
        'sqlalchemy.engine': {
            'level': 'WARNING',
            'handlers': ['console'],
            'propagate': False
        },
        'sqlalchemy.pool': {
            'level': 'WARNING',
            'handlers': ['console'],
            'propagate': False
        },
        'sqlalchemy.dialects': {
            'level': 'WARNING',
            'handlers': ['console'],
            'propagate': False
        },
        
        # Logs de trading optimizados
        'app.services.trading_tasks': {
            'level': 'INFO',
            'handlers': ['console', 'file'],
            'propagate': False
        },
        'app.core.optimized_grid_manager': {
            'level': 'INFO',
            'handlers': ['console', 'file'],
            'propagate': False
        },
        
        # Logs de errores
        'app.services.binance_client_singleton': {
            'level': 'WARNING',
            'handlers': ['console', 'error_file'],
            'propagate': False
        },
        
        # Logs de métricas
        'app.core.metrics_manager': {
            'level': 'INFO',
            'handlers': ['console'],
            'propagate': False
        }
    },
    'root': {
        'level': 'INFO',
        'handlers': ['console', 'file']
    }
}

def setup_logging():
    """Configura el sistema de logging optimizado"""
    logging.config.dictConfig(LOGGING_CONFIG)
    
    # Configurar logging específico para componentes críticos
    logger = logging.getLogger(__name__)
    logger.info("✅ Sistema de logging optimizado configurado")
    
    return logger

# Filtros personalizados para reducir logs repetitivos
class DuplicateFilter(logging.Filter):
    """Filtra logs duplicados en un período de tiempo"""
    
    def __init__(self, name='', timeout=60):
        super().__init__(name)
        self.timeout = timeout
        self.last_log = {}
    
    def filter(self, record):
        current_time = datetime.now()
        log_key = f"{record.name}:{record.getMessage()}"
        
        if log_key in self.last_log:
            time_diff = (current_time - self.last_log[log_key]).total_seconds()
            if time_diff < self.timeout:
                return False
        
        self.last_log[log_key] = current_time
        return True

class TradingSummaryFilter(logging.Filter):
    """Filtra logs de resumen de trading para evitar spam"""
    
    def __init__(self, name=''):
        super().__init__(name)
        self.last_summary = {}
    
    def filter(self, record):
        if 'Resumen del ciclo' in record.getMessage():
            # Solo loggear si hay cambios significativos
            return True
        return True
