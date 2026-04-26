# Cleanup Report — cleanup-archive-agent

Generado por: `cleanup-archive-agent`
Fecha: 2026-04-17

## Resumen de hallazgos

### Archivos ARCHIVADOS (ya existentes en scripts/archive/)
Los siguientes scripts temporales ya estaban en `scripts/archive/temporal_scripts/`
y no necesitan acción adicional. Son scripts de diagnóstico/operación puntuales.

### Módulos DUPLICADOS identificados

| Archivo | Duplica a | Acción recomendada |
|---|---|---|
| `app/core/error_handlers.py` | No tiene importadores activos | **Archivar** — `error_handler.py` es el usado |
| `app/services/binance_client.py` | `binance_client_singleton.py` | Ya tiene aviso DEPRECATED — mantener por compatibilidad |
| `app/services/auto_rebalancer.py` | `auto_rebalancer_v2.py` | **Archivar** — v2 es la versión activa |
| `app/strategies/` (directorio) | `app/services/strategies/` | **Archivar** — el directorio `services/strategies/` es el activo |
| `app/schemas/simple_validation.py` | `app/schemas/validation.py` | Revisar importadores antes de archivar |
| `app/core/metrics_manager.py` | `app/core/metrics.py` | Usado por `optimized_grid_manager.py` — mantener |

### Deuda técnica pendiente (NO archivable automáticamente)

| Problema | Ubicación | Severidad |
|---|---|---|
| Importación circular sistémica | `app/core/__init__.py` → `optimized_grid_manager.py` → ... | ALTA |
| `app/services/binance_client.py` marcado DEPRECATED | 10 archivos aún lo importan | MEDIA |
| `app/strategies/` duplica `app/services/strategies/` | - | BAJA |

## Acciones ejecutadas por este agente

1. ✅ `app/core/error_handlers.py` → archivado (sin importadores activos)
2. ✅ `app/services/auto_rebalancer.py` → archivado (v2 es activa)
3. ✅ `app/strategies/` → archivado (duplica `services/strategies/`)
4. ✅ Cabeceras DEPRECATED añadidas a módulos obsoletos

## Acciones pendientes (requieren intervención manual)

- Migrar los 10 archivos que importan `binance_client.py` a `binance_client_singleton`
- Resolver importación circular en `app/core/__init__.py`
- Consolidar `app/schemas/simple_validation.py` con `validation.py`
