# Breakers — alcance de proceso (B5)

Paper-safe. S-BREAKERS (#51) unificó el estado **in-process** vía `get_shared_breakers()`. Residual B5: API FastAPI y worker Celery son procesos distintos.

## Veredicto

| Opción | Estado | Notas |
|--------|--------|-------|
| **A — Redis HASH compartido** | **Go (MVP)** | Redis ya está en Compose/Celery (`REDIS_URL`). Persistimos trips/open + cooldown anti-flap. |
| B — Alerta en restart + doc | Diferido | Solo si Redis no estuviera disponible; no cierra el hueco de estado. |

## Contrato

| Clave Redis | Tipo | Contenido |
|-------------|------|-----------|
| `gridbot:breakers:v1` | HASH | field = nombre breaker; value = JSON (`active`, `activated_at`, `reason`, `last_activation_ts`, `last_activation_reason`, `activation_count`) |

| Env | Default | Efecto |
|-----|---------|--------|
| `CB_SHARED_STORE` | `auto` | `auto` → Redis si ping OK, si no memory; `redis` / `memory` forzados |
| `CB_COOLDOWN_SECONDS` | `300` | Anti-flap (B4); el timestamp/razón viven en el store |

Módulo: `app/core/breaker_state_store.py`. Wiring: `CircuitBreakers(store=...)` + `get_shared_breakers()`.

## Fail-soft

- Lectura/escritura Redis fallida → log + `breaker_store_sync_errors_total{op=...}`; el proceso sigue con estado local.
- Tests unitarios: `CB_SHARED_STORE=memory` (fixture B5 / `reset_shared_breakers`).

## Métricas

- `breaker_store_backend{backend="redis|memory"}` — qué backend está activo.
- `breaker_store_sync_errors_total{op}` — errores de sync.

## Residual

- No hay pub/sub: cada consulta hace HGETALL (aceptable para frecuencia de breakers).
- Contadores Prometheus siguen siendo por proceso (edge-trigger local); el estado open/closed sí es compartido.
- No toca `grid_config_paper_l0*` ni freeze L0.
