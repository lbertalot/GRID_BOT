## Catálogo de Métricas Prometheus

| Métrica | Tipo | Labels | Origen | Descripción |
|---|---|---|---|---|
| trades_executed_total | Counter | symbol, strategy, side | app/core/metrics.py | Total de trades ejecutados |
| active_breakers_total | Gauge | – | app/core/metrics.py | Cantidad de breakers activos |
| roi_daily_percent | Gauge | strategy | app/services/metrics_service.py | ROI diario estimado |
| profit_total_usdt | Gauge | strategy | app/core/metrics.py | Ganancia acumulada (USDT) |
| profit_daily_usdt | Gauge | strategy | app/core/metrics.py | Ganancia diaria (USDT) |
| api_rate_limit_hits_total | Counter | endpoint | app/core/metrics.py | Golpes a límites de rate |
| cycle_phase | Gauge | phase | app/core/metrics.py | Heartbeat de fase del ciclo |
| http_requests_total | Counter | method, path, status | app/core/middleware/prometheus_http.py | Total de requests HTTP (path normalizado) |
| http_request_duration_seconds | Histogram | method, path, status | app/core/middleware/prometheus_http.py | Latencia de requests HTTP (path normalizado) |
| api_retries_total | Counter | endpoint, reason | app/exchanges/binance_client.py | Reintentos de API (cliente mejorado) |

### Consultas útiles
```promql
sum by (strategy) (profit_total_usdt)
rate(trades_executed_total[5m])
max_over_time(active_breakers_total[15m])
sum by (path) (rate(http_requests_total[5m]))
histogram_quantile(0.99, sum by (le, path) (rate(http_request_duration_seconds_bucket[5m])))
```


