
# Configuración principal de logging optimizada
import logging.config
import os

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
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'level': 'WARNING',
            'formatter': 'detailed',
            'stream': 'ext://sys.stdout'
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'level': 'INFO',
            'formatter': 'detailed',
            'filename': 'logs/trading.log',
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
        # SQLAlchemy - solo warnings y errores
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
        
        # Trading system - información consolidada
        'trading_system': {
            'level': 'INFO',
            'handlers': ['console', 'file'],
            'propagate': False
        },
        
        # API errors - con contexto
        'app.services.binance_client_singleton': {
            'level': 'WARNING',
            'handlers': ['file', 'error_file'],
            'propagate': False
        },
        
        # Metrics - resumidos
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

def setup_optimized_logging():
    """Configura el sistema de logging optimizado"""
    # Crear directorio de logs si no existe
    os.makedirs('logs', exist_ok=True)
    
    # Aplicar configuración
    logging.config.dictConfig(LOGGING_CONFIG)
    
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
