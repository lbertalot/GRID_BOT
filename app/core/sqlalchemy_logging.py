# Configuración específica para SQLAlchemy logging
import logging


def configure_sqlalchemy_logging():
    """Configura el logging de SQLAlchemy para reducir verbosidad"""

    # Reducir logs de SQLAlchemy a solo warnings y errores
    sqlalchemy_logger = logging.getLogger("sqlalchemy.engine")
    sqlalchemy_logger.setLevel(logging.WARNING)

    sqlalchemy_pool_logger = logging.getLogger("sqlalchemy.pool")
    sqlalchemy_pool_logger.setLevel(logging.WARNING)

    sqlalchemy_dialects_logger = logging.getLogger("sqlalchemy.dialects")
    sqlalchemy_dialects_logger.setLevel(logging.WARNING)

    sqlalchemy_orm_logger = logging.getLogger("sqlalchemy.orm")
    sqlalchemy_orm_logger.setLevel(logging.WARNING)

    # Configurar handler específico para SQLAlchemy
    sqlalchemy_handler = logging.StreamHandler()
    sqlalchemy_handler.setLevel(logging.WARNING)

    # Formatter específico para SQLAlchemy
    formatter = logging.Formatter(
        "%(asctime)s | SQLAlchemy | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    sqlalchemy_handler.setFormatter(formatter)

    # Aplicar handler a todos los loggers de SQLAlchemy
    for logger_name in [
        "sqlalchemy.engine",
        "sqlalchemy.pool",
        "sqlalchemy.dialects",
        "sqlalchemy.orm",
    ]:
        logger = logging.getLogger(logger_name)
        logger.handlers.clear()  # Limpiar handlers existentes
        logger.addHandler(sqlalchemy_handler)
        logger.propagate = False  # Evitar propagación al logger raíz

    print("✅ Configuración de SQLAlchemy aplicada")


# Aplicar configuración inmediatamente
configure_sqlalchemy_logging()
