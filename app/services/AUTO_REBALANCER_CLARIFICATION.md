# AutoRebalancer Services - Clarificación

## ⚠️ Nota Importante

Los archivos `auto_rebalancer.py` y `auto_rebalancer_v2.py` **NO son duplicados**. Son servicios complementarios con propósitos distintos:

### `auto_rebalancer.py` (v1) - Grid Asset Rebalancer
- **Propósito**: Rebalancea saldos entre activos de grid trading
- **Uso**: `rebalancing_tasks.check_and_rebalance()` (Celery beat cada hora)
- **Función**: Mantiene saldos operativos en todos los assets de grid
- **Ubicación**: `app/services/rebalancing_tasks.py`

### `auto_rebalancer_v2.py` (v2) - Liquidity Manager
- **Propósito**: Gestiona liquidez general vendiendo activos no estratégicos
- **Uso**: `trading_tasks.trading_cycle_tick()` (Celery beat cada minuto)
- **Función**: Mantiene liquidez en USDT vendiendo activos de baja prioridad
- **Ubicación**: `app/services/trading_tasks.py`

## ✅ Ambos están activos en producción

No deprecar ninguno. Para evitar confusión futura, considerar renombrar a:
- `auto_rebalancer.py` → `grid_asset_rebalancer.py`
- `auto_rebalancer_v2.py` → `liquidity_manager.py`

## Estado de Auditoría

**Hallazgo Auditado**: RESUELTO - No es un duplicado, es diseño intencional.
