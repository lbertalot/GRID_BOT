# GridBot Market View — evaluación y mejora (2026-08-26)

| Campo | Valor |
|-------|--------|
| UID | `gridbot-market-view` |
| URL | http://localhost:3000/d/gridbot-market-view/gridbot-market-view |
| Datasource | PostgreSQL (`uid: postgres`) |

## Diagnóstico del tablero anterior

| Problema | Causa | Fix |
|----------|--------|-----|
| “Candlestick” sin velas, solo triángulos verdes | OHLC se armaba con `trades` (fills escasos del bot) | Velas desde `klines_data` (API pública Binance) |
| Volumen = qty bot | Misma causa | Volumen de exchange en panel inferior; qty bot aparte |
| Ticker 24h sobre trades | Proxy engañoso | High/Low/Δ% desde closes/high/low de klines |
| Tabla con columnas truncadas | Sin `custom.width` | Widths fijos + `round()` en SQL |
| Placeholder `market_ticks` vacío | Tabla inexistente | Eliminado; `klines_data` es el SoT de mercado |
| Datos se envejecían | Sync no periódico | Beat `sync-market-klines-eth` cada 5 min |

## Fuentes de datos (separadas a propósito)

1. **Mercado (Binance público)** → tabla `klines_data` vía `sync_klines_data` / task `sync_market_klines`.
2. **Decisiones del bot** → anotaciones + tabla desde `trades` (BUY verde / SELL rojo).

## Consulta candlestick (activa)

```sql
SELECT
  open_time AS time,
  open_price::float8 AS open,
  high_price::float8 AS high,
  low_price::float8 AS low,
  close_price::float8 AS close
FROM klines_data
WHERE $__timeFilter(open_time)
  AND upper(symbol) = upper('$symbol')
  AND interval = '$candle'
ORDER BY open_time ASC;
```

Variables: `$symbol`, `$candle` ∈ {1m, 5m, 1h}. Rango default del dashboard: **now-3d** (Binance sync trae hasta 1000 velas ≈ 3.5d en 5m).

## Ops

```bash
# sync manual
docker compose -f docker-compose.local.yml exec -T worker \
  bash -c 'cd /app && PYTHONPATH=/app python3 -c "
import asyncio
from app.services.binance_data_sync import binance_sync
async def m():
  for iv in (\"1m\",\"5m\",\"1h\"):
    print(await binance_sync.sync_klines_data(\"ETHUSDT\", iv, 1000))
asyncio.run(m())
"'

# recargar Grafana tras editar JSON
docker compose -f docker-compose.local.yml restart grafana
```

Paper-only. **PROMOTE_LIVE: NO.**
