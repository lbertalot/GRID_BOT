"""
Core package exports.

Evita imports pesados al cargar `app.core` para prevenir ciclos de import
durante inicialización de módulos (por ejemplo en tests unitarios).
"""

__all__ = []
