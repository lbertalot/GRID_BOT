## RFC — Plan técnico de corrección y endurecimiento GridBot v2.5

### Resumen de cambios implementados en esta iteración

- Ciclo 5m orquestado (4m evaluación + 1m ejecución) con métricas `cycle_phase_timestamp`, `cycle_decision_ready`, `cycle_order_executed`.
- Reconciliación endurecida: `portfolio_total_value_usdt` valora (free+locked), `balance_discrepancy_usd` reporta 0 cuando no hay contabilidad interna (evita falsos positivos) y breaker solo se activa si hay contabilidad y gap > umbral.
- Métricas y dashboard:
  - `roi_daily_percent` y `profit_daily_usdt` se publican explícitamente (evita No data).
  - Nueva métrica `portfolio_change_usdt{strategy="grid"}` (delta vs baseline persistente en BD) y panel "Δ Portafolio (USDT)".
  - Endpoint para resetear baseline: `POST/GET /api/v1/metrics/baseline/reset` (token opcional `DASH_RESET_TOKEN`).
- Alerting Prometheus:
  - Reglas de discrepancia usan `balance_discrepancy_usd` con `for: 6m`.
  - Nuevas alertas: `GridBotNoExecutionWithDecisions` (15m) y `GridBotTickStalled` (10m).
- Telegram anti-spam: dedupe + cooldown configurable (`TELEGRAM_COOLDOWN_SECONDS`).
- Alerta -2015 (IP no autorizada): envía IP pública detectada y sugerencia de whitelisting; métrica `external_auth_failures_total`.
- Resiliencia Binance:
  - Métrica `binance_api_errors_total{code,phase}`.
  - "Circuit open" para llamadas privadas tras 3 fallos consecutivos (omitir 5m; variables `BINANCE_PRIVATE_FAIL_THRESHOLD`, `BINANCE_PRIVATE_CIRCUIT_OPEN_SECONDS`).
- PnL realizado: al SELL se cierra el último BUY abierto y se registra `exit_price` y `profit_loss` en `trades` (habilita Ganancia Total/Diaria real).

### Motivación

Reducir falsos positivos de integridad y discrepancia, mejorar la visibilidad del desempeño (distinción entre PnL realizado vs revalorización), y endurecer la resiliencia a fallos externos (DNS, límites de API/IP) sin degradar la disponibilidad del sistema.

### Diseño

1) Reconciliación y Breakers
- Si `int_usdt==0` (sin contabilidad interna), publicar `balance_discrepancy_usd=0` y no activar breakers por discrepancia.
- Al tener contabilidad, activar breaker según gap relativo > umbral.

2) Métricas y Baseline
- Persistencia en `system_settings` de `profit:baseline_iso` y `portfolio:baseline_value_usdt`.
- `portfolio_change_usdt = portfolio_actual - baseline_portfolio`.
- Endpoint de reset (GET/POST) para uso desde Grafana.

3) Alertas y Dashboard
- Migrar reglas a `balance_discrepancy_usd`, `for: 6m`.
- Alertas de ciclo (sin ejecución con decisiones listas y tick detenido).
- Paneles: Δ Portafolio, Segundos desde última evaluación.

4) Telegram y Anti-spam
- Dedupe por hash del mensaje con cooldown (por defecto 10 min) y edge-trigger de circuit breakers.

5) Binance resiliencia
- Métrica de errores con etiquetas (código, fase).
- IP inválida (-2015): notificación con IP pública, cooldown 30 min.
- Circuit breaker "privado" (interno) para llamadas `get_account` tras N fallos.

6) PnL Realizado
- A nivel `OptimizedGridManager`, cerrar BUY al SELL y registrar `profit_loss`. Adapta métricas de ganancia.

### Consideraciones de Seguridad
- El endpoint GET de reset baseline puede protegerse con `DASH_RESET_TOKEN`.
- Edge-trigger y cooldown reducen spam de alertas.

### Plan de despliegue
- Variables nuevas opcionales: `TELEGRAM_COOLDOWN_SECONDS`, `BINANCE_PRIVATE_FAIL_THRESHOLD`, `BINANCE_PRIVATE_CIRCUIT_OPEN_SECONDS`, `DASH_RESET_TOKEN`.
- Recargar Prometheus y Grafana para nuevas reglas/paneles.

### Trabajo Futuro
- Integrar contabilidad interna para `int_usdt` y activar discrepancias reales.
- Panel de PnL realizado por día y WinRate 7d.

Fecha: 2025-09-04
Autor: Equipo Plataforma / Trading
Estado: En progreso
Impacto: Alto (bloqueante para reactivar trading real)

### Motivación
Las auditorías detectaron discrepancias severas entre el balance/PnL reportado por el sistema y Binance real, fallos no registrados, y una validación de balance que no se ejecuta E2E pese a pasar pruebas unitarias. Se requiere un plan técnico exhaustivo para restaurar la integridad y confiabilidad antes de reactivar trading real.

### Objetivos
- Eliminar discrepancias de balance/PnL con reconciliación determinística.
- Garantizar validación E2E previa al envío de órdenes (precisión, filtros, balance, notional, límites de riesgo).
- Asegurar tracking idempotente y registro completo de fallos y fills parciales.
- Endurecer circuit breakers y modo de emergencia con verificación previa de integridad. Middleware `IntegrityGuardMiddleware` en FastAPI bloquea rutas críticas si hay breakers activos; endpoint `/breakers/summary` publica estado.

### Alcance
- Núcleo de ejecución, tracking, reconciliación y observabilidad. No cubre nuevos exchanges/estrategias.

### Diseño propuesto

1) Capa de normalización de símbolos y precisión
- Módulo `core/precision.py` con cache de `exchange_info` por símbolo.
- Funciones puras: `round_price(symbol, price)`, `round_qty(symbol, qty)`, `validate_notional(symbol, price, qty)`.
- Actualización periódica del cache (TTL configurable) y warm-up en startup.

2) Validación E2E de órdenes (guard clauses)
- Dependencia FastAPI `get_order_validator()` inyectando validadores: precisión, LOT_SIZE, PRICE_FILTER, MIN_NOTIONAL, balance suficiente, límites de riesgo.
- Reglas: early return con error estructurado; logging y métrica de motivo de rechazo.
- Sourcing de límites desde exchange: `stepSize`, `minQty`, `minNotional` para cada símbolo; ajuste de cantidades (step) y notional efectivo `max(env, exchange)`.
- Bloqueo duro si `IntegrityMonitor` indica estado no sano.

3) Reconciliación determinística con Binance
- Job asíncrono periódico (≤60s):
  - Obtener balances, posiciones, órdenes recientes; comparar con ledger interno.
  - Detectar faltantes (fallos no registrados, fills parciales) y ajustar libro interno con asientos de corrección.
  - Registrar diferencias en `integrity_monitor` y emitir métricas (`balance_discrepancy`, `unaccounted_pnl`).
  - Exponer `cash_usdt`/`portfolio_total_usdt` y publicar métricas `portfolio_total_value_usdt`/`cash_balance_usdt`.
- Alarma crítica y `breakers.protect()` si discrepancia > umbral.

4) Tracking idempotente y completo
- `OperationTracker` con claves idempotentes (`client_order_id`) y estados: intended -> submitted -> accepted -> partially_filled -> filled -> canceled -> failed.
- Registro explícito de fallos y parciales; correlación con respuestas/WS.
- Reintentos con backoff solo si la operación es segura e idempotente.

5) Circuit breakers endurecidos y modo emergencia
- Umbrales por activo/global: pérdida diaria, DD, discrepancia, ratio de fallos.
- Acciones automáticas: reducir tamaño, congelar nuevas órdenes, cerrar posiciones, `emergency_stop`.
- Al salir de emergencia: checklist de integridad (reconciliación=OK, pruebas=OK, métricas estables).

6) Observabilidad y métricas
- Prometheus: latencia por etapa (validación, envío, confirmación, reconciliación), slippage, fees, discrepancia, ratio de fallos, fills parciales.
- Finanzas: `portfolio_total_value_usdt`, `cash_balance_usdt`, breakers activos (`active_breakers_total`).
- Logs estructurados con `order_id`, `client_order_id`, `symbol`, `state`.
- Dashboards Grafana: Integridad, Ejecución, Riesgo.

7) Pruebas y calidad
- Tests unitarios de normalización/validación; integración E2E de ruta de orden con mocks de Binance.
- Test de reconciliación contra snapshot simulado de Binance con discrepancias.
- Cobertura ≥ 85% y pruebas críticas 100%.

### Cambios en API (FastAPI)
- Middleware de integridad: rechaza requests si `system_state != HEALTHY/PROTECTED`.
- Endpoints de estado: `/integrity/status`, `/breakers/summary`, `/reconciliation/summary`.
- Respuestas de error estandarizadas con códigos y `reason`.

### Plan de migración
- Fase 0: Mantener `EMERGENCY_STOP` y papel; bloquear real.
- Fase 1: Implementar normalización y validación E2E; habilitar en papel; monitorear 72h.
- Fase 2: Implementar reconciliación y tracking idempotente; validar 72h.
- Fase 3: Endurecer breakers; dashboards; pruebas E2E; cobertura.
- Fase 4: Activación gradual real: 5% tamaño -> 10% -> 25% con SLOs.

### Riesgos
- Latencia adicional por validación y reconciliación → mitigar con cache y asincronía.
- Inconsistencias por WS/API de exchange → preferir fuentes canónicas y re-intentos con jitter.

### Criterios de aceptación
- Discrepancia de balance ≤ 0.1% por 24h; 0 fallos no registrados; 0 errores de precisión; slippage y fees contabilizados 100%; pruebas críticas 100%.

### Métricas de salida
- `balance_discrepancy`, `unaccounted_pnl`, `order_validation_rejects{reason}`, `order_fail_ratio`, `partial_fill_ratio`, `reconciliation_latency_seconds`.

### Trabajo a realizar (alto nivel)
- Módulos: `core/precision.py`, `core/reconciliation.py`, `routers/integrity_routes.py`, `routers/breakers_routes.py`.
- Ampliar `core/operation_tracker.py` y `core/integrity_monitor.py`.
- Middleware `core/middleware/integrity_guard.py`.
- Dashboards: Integridad, Ejecución, Riesgo.

### Rollback
- Revertir a papel; activar `emergency_stop`; deshacer despliegue; restaurar configs previas.



## Implementaciones realizadas (2025-09-07)
- Validación robusta de credenciales/conectividad Binance en Singleton y en startup; breakers activados ante fallo y endpoint `/breakers/summary` expuesto.
- Filtrado de metadatos en carga de grids (`optimized_grid_manager`, `auto_rebalancer`) evitando errores de validación/símbolo.
- Normalización/regex de símbolos y manejo `APIError -1100` en cliente.
- Guard clauses en ciclo de trading para evitar `NoneType` y abortar con cliente no listo.
- Bugfix `AutoRebalancer.get_usdt_balance` (variables no definidas) y corrección del label `mode` en resúmenes de ciclo.
- Mecanismo de preflight: `POST /api/simulations/dry-run` (PAPER) y `make dry-run` para validación/Simulación sin enviar órdenes.
- Endpoint `GET /api/reconciliation/summary` publica `cash_usdt` y `portfolio_total_usdt`. Reglas de alertas Prometheus: discrepancia > 1%/5 USDT y API Down 5m/15m.

### Fase 1 — Capa de normalización y validación E2E
- Implementado `core/precision.py` con caché de `exchange_info` y funciones puras (`round_price`, `round_quantity`, `validate_notional`).
- Integrada validación previa en `api/trade.py`: ajuste de precisión, chequeo de `minNotional` y balance suficiente; early return 400 con motivo.
- Métrica `order_validation_rejects_total{reason,symbol}` para seguimiento de rechazos.
- Próximo: incorporar bloqueo por breaker en la dependencia de validación (cuando `system_state` no sea HEALTHY/PROTECTED).

## Próximos pasos
- Provisioning/renderer Grafana y dashboards de Integridad/Ejecución.
- Debounce de logs y métricas de rechazo/fallos externas.
- Playbooks de operación (credenciales, Grafana) y gates automáticos post-deploy usando dry-run.