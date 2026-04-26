# Pipeline API->DB Runbook

## Objetivo
Diagnosticar rápido si un problema está en consumo API, procesamiento o persistencia DB.

## Señales mínimas
- `pipeline_api_requests_total{endpoint,status}`
- `pipeline_api_request_latency_seconds`
- `pipeline_events_processed_total{stage}`
- `pipeline_events_dropped_total{stage,reason}`
- `db_writes_total{table,operation,status}`
- `pipeline_errors_total{stage,error_type}`

## Alertas operativas
- `TradesNoInserts60m`
- `PipelineAuthErrorsBurst`
- `PipelineTimeoutErrorsBurst`
- `PipelineConstraintErrors`
- `PipelineHighDropRatio`

## Diagnóstico rápido (5-10 min)
1. **Verificar consumo API**
   - PromQL:
     - `sum(rate(pipeline_api_requests_total{status="success"}[5m]))`
     - `sum(rate(pipeline_api_requests_total{status="failure"}[5m]))`
   - Si success ~0 y failure alto: revisar credenciales, red, timeouts.

2. **Verificar procesamiento**
   - PromQL:
     - `sum(increase(pipeline_events_processed_total[15m]))`
     - `sum(increase(pipeline_events_dropped_total[15m]))`
   - Si processed > 0 y dropped ratio >70%: revisar filtros de negocio y reglas.

3. **Verificar persistencia DB**
   - PromQL:
     - `sum(increase(db_writes_total{table="trades",status="ok"}[60m]))`
     - `sum(increase(db_writes_total{table="balances",status="ok"}[60m]))`
   - Si writes=0: revisar `pipeline_errors_total{error_type="constraint|timeout|auth"}` y logs.

4. **Correlación en logs**
   - Filtrar por `correlation_id` retornado en header `X-Correlation-ID`.
   - Buscar eventos:
     - `sync_recent_trades.fetch_completed`
     - `sync_recent_trades.persist_completed`

## Queries SQL de soporte
```sql
-- actividad última hora por tablas críticas
SELECT 'trades' table_name, COUNT(*) rows_1h
FROM public.trades WHERE "timestamp" >= now() - interval '1 hour'
UNION ALL
SELECT 'balances', COUNT(*) FROM public.balances WHERE updated_at >= now() - interval '1 hour'
UNION ALL
SELECT 'alerts', COUNT(*) FROM public.alerts WHERE created_at >= now() - interval '1 hour'
UNION ALL
SELECT 'portfolio_snapshots', COUNT(*) FROM public.portfolio_snapshots WHERE captured_at >= now() - interval '1 hour';
```

## Acciones por tipo de error
- `auth`: validar API keys, IP whitelist, permisos, reloj NTP.
- `timeout`: revisar conectividad y ajustar retry/backoff/timeout.
- `constraint`: revisar migraciones y tipos (ej. `order_id`, `NOT NULL`, `CHECK`).
- `parse`: validar cambios de payload del proveedor.
