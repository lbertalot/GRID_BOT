## PRD — GridBot v2.5 “Fortaleza Adaptativa”

Fecha: 2025-09-04
Versión del documento: 1.0

### Resumen ejecutivo
GridBot v2.5 es un sistema de trading algorítmico (FastAPI + Celery) orientado a bajo riesgo con defensas activas, sizing adaptativo por Kelly Fraccional y observabilidad robusta (Prometheus/Grafana). Este PRD define el producto, alcance, requisitos funcionales y no funcionales, flujos, KPIs y el estado actual del sistema con todos los errores y hallazgos reportados.

### Objetivos del producto
- **Defensa primero**: Validar toda orden contra `exchange_info` (PRICE_FILTER, LOT_SIZE, MIN_NOTIONAL) y límites duros.
- **Adaptabilidad**: Ajustar estrategia y sizing por régimen de mercado (ML) y volatilidad (ATR).
- **Ciencia del sizing**: Kelly Fraccional con límites conservadores y controles de riesgo.
- **Observabilidad total**: Métricas por orden (lag, slippage, fees), exposición, drawdown, circuit breakers, integridad.

### Alcance v2.5
- Trading Grid en `BTCUSDT`, `ETHUSDT`, `BNBUSDT` con modos Paper/Real y perfiles `minimal/optimized/safe`.
- **Defensas**: Circuit breakers multi-nivel, validación de precisión/cantidades/nominal, verificación de balance previo a enviar orden.
- **Operacional**: Modo emergencia con stop global, Telegram Bot para alertas, métricas Prometheus, tablero Grafana.
- **Integridad**: BalanceValidator, OperationTracker, IntegrityMonitor.

### Usuarios y casos de uso
- **Trader/Prop**: Activar/desactivar activos, revisar PnL, aceptar recomendaciones.
- **SRE/DevOps**: Operar despliegues, revisar métricas/alertas, ejecutar parada de emergencia.
- **Quant/ML**: Inyectar señales de régimen, calibrar Kelly, validar resultados.

### Requisitos funcionales
- **Orden/Trade**
  - Validación previa con filtros de exchange y precisión de cantidad/precio.
  - Verificación de balance y notional mínimo antes de enviar.
  - Envío asíncrono, manejo de fills parciales, tracking idempotente por `client_order_id`.
  - Cálculo y registro de slippage y fees en la ejecución real.
- **Circuit Breakers**
  - Umbrales por activo y globales: pérdida diaria, drawdown acumulado, discrepancia de integridad.
  - Modos: normal, protegido, crítico, emergencia (stop total).
  - Acciones: reducir tamaño, congelar nuevas órdenes, cerrar posiciones, stop.
- **Monitoreo/Alertas**
  - Métricas: latencia API, ratio de éxito, fills parciales, discrepancia de balances, PnL diario.
  - Alertas: pérdidas > umbral, fallos de orden, divergencia sistema vs Binance, fallos de integridad.
- **Integridad**
  - Reconciliación periódica de balances y PnL con Binance.
  - Registro de operaciones fallidas y parciales; no perder eventos.
  - Auditoría exportable (JSON) y resúmenes horarios.

### Requisitos no funcionales
- **Rendimiento**: P99 de respuesta API < 250 ms (operaciones locales), colas asíncronas para I/O hacia exchange.
- **Confiabilidad**: Tolerancia a fallos de red, reintentos exponenciales, idempotencia.
- **Seguridad**: Manejo seguro de credenciales, permisos mínimos, firma HMAC.
- **Escalabilidad**: Workers horizontales, colas desacopladas.
- **Observabilidad**: Métricas, logs estructurados, trazas, tableros Grafana.

### Flujos clave
- **Flujo de envío de orden**: validación -> verificación de balance -> cálculo de tamaño -> envío -> tracking -> reconciliación -> métricas/alertas.
- **Flujo de emergencia**: disparo por umbral o discrepancia -> activar breakers -> suspender trading -> alertar -> auditoría -> restauración controlada.
- **Flujo de reconciliación**: obtener balances/posiciones reales -> comparar con ledger interno -> ajustar PnL y estado -> registrar diferencias.

### Estados operativos
`PAPER`, `REAL`, `PROTECTED`, `CRITICAL`, `EMERGENCY_STOP`. Transiciones gobernadas por IntegrityMonitor y circuit breakers. Además, el middleware `IntegrityGuardMiddleware` bloquea rutas de trading cuando hay breakers activos.

### Configuración
- Perfiles en `grid_config_minimal.json`, `grid_config_optimized.json`, `grid_config_safe.json`.
- Límite de riesgo por activo y global, tamaños base y máximos, parámetros de ATR y Kelly Fraccional.

### Métricas/KPIs mínimos
- PnL diario y acumulado, slippage medio, ratio de éxito, latencia de ejecución, exposición por activo, drawdown, discrepancia de balances, número de órdenes fallidas/no registradas, alarmas.
- Finanzas en tiempo real: `portfolio_total_value_usdt`, `cash_balance_usdt`; breakers activos `active_breakers_total`.

---

## Estado actual del sistema (consolidado)

### Resumen de seguridad y estabilidad
- `real_trading_safety_validation.json` (2025-09-04 11:23:56):
  - overall_safety_status: SAFE; stability_score: 80; readiness: READY; balance reportado: 408.78 USD; cambio +29.03%.
- `massive_stabilization_report.json` (2025-09-02 22:16:10):
  - estabilidad total: 80; impacto de estabilización: +5 pts; trades añadidos: 24; balance sin cambio.
- `intensive_monitoring_report_20250902_221258.json`:
  - score: 75; readiness: CASI LISTO; balance pasó 1000.0 -> 917.385 (-8.26%).
- `monitoring_summary_20250902_214642.json`:
  - estabilidad: 75; alertas: 0; 22.46 h de monitoreo.

Conclusión: los reportes de estabilidad muestran 75–80/100 y mensajes de listo/casi listo, pero existen contradicciones severas con los reportes de integridad y emergencia.

### Hallazgos críticos de integridad
- `complete_system_audit_report.json` (2025-09-04 14:39:13):
  - Discrepancia total: 296.79 USD; PnL discrepante: 31.72; pérdidas no contabilizadas: 39.95.
  - Binance real: 317.13 USD, PnL día: -8.83; Sistema reporta: 408.78 USD (+29.03%).
  - 3 operaciones fallidas no registradas: insuficiente balance, orden no llenada, precio fuera de rango.
  - Issues: CRÍTICO discrepancia masiva; ALTO operaciones fallidas no registradas; ALTO PnL incorrecto; MEDIO monitoreo desincronizado.
  - Recomendación: SUSPENDER trading real, verificación cruzada de balances y auditoría forense.
- `emergency_stop_report.json` (2025-09-04 14:34:03):
  - Tipo: DISCREPANCIA_CRÍTICA_BALANCE; sistema reportado 408.78 vs real 317.10; discrepancia -22.4%.
  - Acciones: trading real suspendido, breakers activados, monitoreo intensivo 24/7.
- `integrity_system_test_report_20250904_151147.json`:
  - 6/7 pruebas PASSED (85.7%); fallo en "balance_validation_simulation": Validación no se ejecutó.
- `integrity_components_test_report_20250904_150550.json`:
  - Componentes núcleo PASSED (BalanceValidator, OperationTracker, IntegrityMonitor). Total 4/4.

Conclusión: Hay una brecha entre pruebas de componentes y comportamiento sistémico (validación de balance no ejecutándose en flujo completo y discrepancias severas con Binance).

### Problemas operacionales y técnicos (listado unificado)
Fuente: `reporte_analisis_problemas.json` (2025-09-01)
- FINANCIERO CRÍTICO: Pérdidas aceleradas (-9.82% día).
- FINANCIERO CRÍTICO: 456 trades abiertos sin cerrar.
- TÉCNICO CRÍTICO: Configuración de emergencia no efectiva (workers continuaron).
- TÉCNICO ALTA: Errores de precisión en cantidades ("Illegal characters in parameter quantity").
- TÉCNICO ALTA: Saldo insuficiente para cerrar trades.
- ARQUITECTURA CRÍTICA: Falta de circuit breakers (en ese momento).
- ARQUITECTURA ALTA: Configuración compleja propensa a errores.
- ARQUITECTURA ALTA: Falta de validación de saldos pre-orden.
- OPERACIONAL ALTA: Falta de monitoreo en tiempo real.
- OPERACIONAL ALTA: Proceso de emergencia manual.
- OPERACIONAL ALTA: Falta de alertas tempranas.

Estado 2025-09-04: circuit breakers, métricas, y alertas han sido implementados y pasan pruebas unitarias/integración; sin embargo, persisten:
- Discrepancias de balance y PnL con Binance.
- Omisiones de registro de fallos y fills parciales.
- Validación de balance no ejecutada en flujo end-to-end.
- Señales de estabilidad inconsistentes vs. auditorías.

### Impacto
- Riesgo de decisiones con datos incorrectos (PnL, balance, exposición).
- Riesgo financiero por órdenes fuera de límites y por no registrar pérdidas efectivas.
- Pérdida de confianza y exigencia de suspensión de trading real.

---

## Requisitos detallados (v2.5 estabilizada)

### Funcionales
- Validación integral por orden: precisión, lot size, price filter, min notional, balance suficiente, límites de riesgo.
- Reconciliación periódica (≤60s) con Binance de balances, PnL y posiciones; corrección de ledger interno.
- Registro idempotente y completo de operaciones (éxito/fallo/parcial) con reintentos y correlación `client_order_id`.
- Circuit breakers multi-umbral automáticos con acciones predefinidas y evidencia en métricas/logs.
- Modo emergencia con recuperación guiada (playbooks) y verificación previa de integridad.
- Alertas multicanal (Telegram) con supresión y severidades.

### No funcionales
- P99 API < 250 ms; bulk I/O hacia exchange asíncrono; colas resilientes.
- Idempotencia y exactamente-una-vez en tracking a nivel aplicación.
- Trazabilidad: cada orden con timeline de eventos y métricas.

### KPIs de aceptación
- Discrepancia de balance ≤ 0.1% sostenida 24h (delta entre `portfolio_total_usdt` y Binance UI).
- Slippage medio ≤ 0.05% en mercados líquidos; fees contabilizadas 100%.
- 0 órdenes con "Illegal characters" y 0 rejects por precision/LOT_SIZE en 72h.
- 0 operaciones fallidas sin registro en 72h.
- Cobertura de pruebas ≥ 85%; 100% de flujos críticos cubiertos.

### Fuera de alcance (v2.5)
- Nuevos exchanges; derivados; estrategias fuera de Grid base.

---

## Roadmap y entregables
- Fase A: Reconciliación y tracking idempotente (bloqueante para real trading).
- Fase B: Validación E2E de balance y precisión; hard stops.
- Fase C: Observabilidad avanzada (dashboards, SLOs) y pruebas integrales.
- Fase D: Re-activación gradual de real trading con guardias reforzadas.

---

## Riesgos y mitigación
- Desincronización con Binance → verificación cruzada y reconciliación agresiva.
- Errores de precisión → normalizador de cantidades/precios por símbolo y cache de `exchange_info`.
- Fallos de red → reintentos con backoff, circuit breaker de proveedor.

---

## Anexos
- Reportes fuente: `complete_system_audit_report.json`, `emergency_stop_report.json`, `real_trading_safety_validation.json`, `integrity_*`, `monitoring_*`, `intensive_monitoring_*`, `massive_stabilization_report.json`, `reporte_analisis_problemas.json`.


## Actualizaciones al 2025-09-07

- Binance validado en producción (whitelist IP aplicada): lectura de balances y cuenta OK.
- Cliente Binance Singleton endurecido con `validate_credentials_and_connectivity()`; breakers expuestos en `/breakers/summary`.
- Correcciones aplicadas:
  - Filtrado de metadatos en `grid_config_optimized.json` (en `optimized_grid_manager` y `auto_rebalancer`).
  - Normalización/regex de símbolos y manejo de `APIError -1100`.
  - Guard clause de readiness del cliente para evitar `NoneType` en trading.
  - Bugfix `AutoRebalancer.get_usdt_balance` y ajuste del label `mode` en resúmenes.
- Nuevas herramientas operativas:
  - Endpoint `POST /api/simulations/dry-run` (siempre PAPER) para preflight validado.
  - Objetivo `make dry-run` que ejecuta simulación dentro del contenedor.
- Validación E2E (modo protegido): ciclo PAPER sin órdenes reales cuando fondos < min_notional, con validación de filtros activa.

### Avances al 2025-09-07 (Fase 1 completada)
- Módulo `core/precision.py` creado con caché de `exchange_info` y funciones puras `round_price`, `round_quantity`, `validate_notional`.
- Validación E2E integrada en `api/trade.py`: ajuste de precio/cantidad según filtros; verificación de `minNotional` y balance disponible antes de enviar; retornos 400 estructurados ante rechazo.
- Métrica Prometheus `order_validation_rejects_total{reason,symbol}` añadida para observabilidad de rechazos.
- Beneficio: eliminación de errores `PRICE_FILTER`/`LOT_SIZE`/`MIN_NOTIONAL` y reducción de fallos por fondos insuficientes en ruta de orden.

### Actualizaciones técnicas recientes (2025-09-07)
- Calibración de tamaños a filtros del exchange (FundManager/OptimizedGridManager): `stepSize`, `minQty` y `minNotional` efectivos por símbolo; ajuste de cantidades y notional mínimo (`max(env, exchange)`).
- Observabilidad financiera: métricas `portfolio_total_value_usdt`, `cash_balance_usdt`; breakers activos con `active_breakers_total`. Endpoint `/api/reconciliation/summary` con `cash_usdt` y `portfolio_total_usdt` alineado con Binance.
- Alertas Prometheus/Alertmanager: discrepancia > 1% o > 5 USDT (5m) y disponibilidad API (warning 5m / critical 15m).
- Grafana: tablero de Rentabilidad corregido (queries con labels, tarjetas de Portfolio/Cash/Breakers, fix “No Data”).
- Despliegue Heroku: `runtime.txt` (python-3.11.10), `.python-version` (3.11) y toolchain (`setuptools`, `wheel`) en `requirements.txt`.

### Próxima iteración del PRD
- Añadir SLOs explícitos (reconciliación, disponibilidad API/worker) y umbrales de breakers por activo.
- KPIs por símbolo (éxito, slippage, fees) y metas operativas.
- Detallar plan de activación gradual de real trading con límites de tamaño/orden y gates automáticos post-deploy.

