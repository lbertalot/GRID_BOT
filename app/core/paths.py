"""
Utilidades para manejo de paths en diferentes entornos (Docker, Heroku, local)
"""

import os
from pathlib import Path


def get_writable_path(base_path: str, fallback_to_tmp: bool = True) -> Path:
    """
    Obtiene un path escribible, ajustando para entornos con filesystem efímero.

    En Heroku, solo /tmp es escribible, así que redirige paths de datos temporales
    a /tmp si el directorio original no es escribible.

    Args:
        base_path: Path base deseado
        fallback_to_tmp: Si True, usa /tmp como fallback si el path no es escribible

    Returns:
        Path escribible
    """
    path = Path(base_path)

    # En Heroku, detectar si estamos en un dyno
    is_heroku = os.getenv("DYNO") is not None

    if is_heroku:
        # En Heroku, usar /tmp para cualquier directorio de datos temporales
        # Solo mantener el nombre del directorio para organización
        path_name = path.name
        tmp_path = Path("/tmp") / path_name
        tmp_path.mkdir(parents=True, exist_ok=True)
        return tmp_path

    # En otros entornos, intentar crear el directorio original
    try:
        path.mkdir(parents=True, exist_ok=True)
        # Verificar que sea escribible
        test_file = path / ".write_test"
        try:
            test_file.write_text("test")
            test_file.unlink()
            return path
        except (PermissionError, OSError):
            if fallback_to_tmp:
                tmp_path = Path("/tmp") / path.name
                tmp_path.mkdir(parents=True, exist_ok=True)
                return tmp_path
            raise
    except (PermissionError, OSError):
        if fallback_to_tmp:
            tmp_path = Path("/tmp") / path.name
            tmp_path.mkdir(parents=True, exist_ok=True)
            return tmp_path
        raise


def get_monitoring_dir() -> Path:
    """Obtiene el directorio de monitoreo (escribible)"""
    base_path = os.getenv("MONITORING_DIR", "monitoring_data")
    return get_writable_path(base_path)


def get_reports_dir() -> Path:
    """Obtiene el directorio de reportes (escribible)"""
    base_path = os.getenv("REPORTS_DIR", "reports")
    return get_writable_path(base_path)


def get_logs_dir() -> Path:
    """Obtiene el directorio de logs (escribible)"""
    base_path = os.getenv("LOG_FILE_PATH", "./logs")
    # Si LOG_FILE_PATH es un archivo, usar su directorio padre
    if Path(base_path).suffix:
        base_path = str(Path(base_path).parent)
    return get_writable_path(base_path)
