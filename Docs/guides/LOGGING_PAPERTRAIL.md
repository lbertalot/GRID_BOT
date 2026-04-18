# Logging y Papertrail (plan free 10 MB/día)

## Objetivo

Ajustar nivel de log y volumen para que la app en Heroku quepa en el plan gratuito de Papertrail (**10 MB/día**, 7 días retención).

## Comportamiento actual

| Proceso | Configuración | Qué va a stdout (→ Papertrail) |
|--------|----------------|----------------------------------|
| **Web** (uvicorn) | `app/main.py` → `LOG_LEVEL` por defecto `WARNING` si `ENVIRONMENT=production`; módulos ruidosos (trading_tasks, optimized_grid_manager, uvicorn.access, etc.) en `WARNING`; `ACCESS_LOG=false` → access log en ERROR | Solo mensajes **WARNING** y superiores |
| **Worker** (Celery) | Al cargar `optimized_grid_manager` se aplica `app/core/optimized_logging.py`: en producción consola con nivel **WARNING**; root y loggers respetan `LOG_LEVEL`/`ENVIRONMENT` | Solo mensajes **WARNING** y superiores |

En **desarrollo** (`ENVIRONMENT=development` o `LOG_LEVEL=INFO`) la consola puede emitir INFO; en **producción** la consola se fuerza a WARNING para limitar volumen.

## Volumen estimado

- **Línea típica**: `%(asctime)s | %(name)s | %(levelname)s | %(message)s` → ~120–250 bytes por línea.
- **Con nivel WARNING y sin access log**:
  - Web: arranque, errores de Binance/breakers, integridad, pocas líneas por hora.
  - Worker: `trading_cycle_tick` cada 60 s, `assess_risk` cada 5 min, etc.; solo se emiten warnings (fallos de API, balances, breakers).
- **Estimación**: ~0,5–2 MB/día (web + worker), muy por debajo de 10 MB/día.

Si se usara **INFO** en consola en producción, solo el worker podría generar del orden de **15–20 MB/día** (muchos `logger.info` por ciclo de trading), por eso en producción se deja consola en WARNING.

## Variables recomendadas (Heroku / producción)

```bash
ENVIRONMENT=production
LOG_LEVEL=WARNING
ACCESS_LOG=false
```

- `ENVIRONMENT=production`: activa nivel WARNING por defecto en `main.py` y consola WARNING en `optimized_logging`.
- `LOG_LEVEL=WARNING`: refuerza que solo se emita WARNING+ a consola.
- `ACCESS_LOG=false`: evita una línea por cada request HTTP (reduce mucho el volumen si hay tráfico).

No es necesario definir `LOG_FILE_PATH` en Heroku: en producción sin `LOG_FILE_PATH` el logging optimizado solo usa consola (stdout), que es lo que Papertrail captura.

## Dónde se configura

- **Global (web)**: `app/main.py` → `_configure_logging()` (root level, módulos ruidosos, uvicorn.access).
- **Worker / grid manager**: `app/core/optimized_logging.py` → `_build_logging_config()`, `setup_optimized_logging()` (nivel consola según `ENVIRONMENT`, root y loggers según `LOG_LEVEL`).

## Resumen

- **Nivel en producción**: WARNING en consola (web y worker).
- **Volumen estimado**: ~0,5–2 MB/día; compatible con Papertrail 10 MB/día.
- **Recomendación**: usar `ENVIRONMENT=production`, `LOG_LEVEL=WARNING` y `ACCESS_LOG=false` en producción.
