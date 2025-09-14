# Contribuir a GridBot

Gracias por tu interés en contribuir. Este proyecto prioriza calidad, seguridad y estabilidad.

## Requisitos previos
- Python 3.11+
- Docker y Docker Compose
- PostgreSQL y Redis (vía docker-compose)

## Flujo de trabajo
1. Crea un fork y una rama (feature/nombre-corto).
2. Instala dependencias: `pip install -r requirements.txt`.
3. (Opcional) Levanta servicios locales: `docker-compose up -d db redis`.
4. Ejecuta pruebas: `pytest --cov=app` (objetivo ≥ 85%).
5. Actualiza documentación si aplica.
6. Abre un Pull Request con descripción clara del cambio.

## Checklist de PR
- [ ] Tests pasan y cobertura ≥ 85%
- [ ] Sin secretos ni `.env` en el cambio
- [ ] Documentación actualizada
- [ ] Métricas/alertas actualizadas si aplica

## Estilo y calidad
- Python 3.11 con type hints
- FastAPI con dependencias y guard clauses
- Pydantic v2 para validación
- Funciones puras preferidas; evitar clases innecesarias

## Seguridad
- Nunca subir `.env` ni secretos.
- Usar secretos de GitHub Actions para CI/CD.

## Código de conducta
Este proyecto adopta un Código de Conducta. Ver `CODE_OF_CONDUCT.md`.
