## Checklist de Reactivación — GridBot v2.5

Fecha: 2025-09-04
Propósito: Validar condiciones mínimas para salir de EMERGENCY_STOP y reactivar trading real de forma gradual.

### A. Integridad y reconciliación (bloqueantes)
- [ ] Reconciliación balances/posiciones/órdenes con Binance ejecutándose cada ≤60s.
- [ ] Discrepancia de balance ≤ 0.1% durante 24 h continuas.
- [ ] PnL diario del sistema concuerda con Binance (±0.1%).
- [ ] 0 operaciones fallidas no registradas en últimas 72 h.
- [ ] Fills parciales registrados y reflejados en ledger interno.

### B. Validación y precisión (bloqueantes)
- [ ] Normalización de precisión de precio/cantidad por símbolo activa (cache exchange_info).
- [ ] Validación E2E previa al envío: PRICE_FILTER, LOT_SIZE, MIN_NOTIONAL, balance suficiente, límites de riesgo.
- [ ] 0 errores de precisión/LOT_SIZE/MIN_NOTIONAL en 72 h.

### C. Circuit breakers y emergencia
- [ ] Umbrales por activo y global configurados: pérdida diaria, drawdown, discrepancia, ratio de fallos.
- [ ] Acciones automáticas probadas: reducir tamaño, congelar, cerrar posiciones, stop total.
- [ ] Simulacro de entrada/salida de emergencia completado y documentado.

### D. Observabilidad y alertas
- [ ] Métricas Prometheus: `balance_discrepancy`, `unaccounted_pnl`, `order_validation_rejects{reason}`, `order_fail_ratio`, `partial_fill_ratio`, `reconciliation_latency_seconds`.
- [ ] Dashboards Grafana: Integridad, Ejecución, Riesgo con SLOs visibles.
- [ ] Alertas Telegram por severidad y supresión funcionando.

### E. Pruebas y calidad
- [ ] Pruebas críticas E2E 100% pasando (orden completa, fallo, parcial, reconciliación, emergencia).
- [ ] Cobertura total ≥ 85% y cobertura de flujos críticos 100%.
- [ ] Pruebas de estrés en papel: 72 h sin violar SLOs.

### F. Activación gradual (Go/No-Go por etapa)
- [ ] Etapa 1 — 5% tamaño nominal, 24 h sin alertas rojas, SLOs OK. Go ☐ / No-Go ☐
- [ ] Etapa 2 — 10% tamaño nominal, 24 h sin alertas rojas, SLOs OK. Go ☐ / No-Go ☐
- [ ] Etapa 3 — 25% tamaño nominal, 48 h sin alertas rojas, SLOs OK. Go ☐ / No-Go ☐
- [ ] Etapa 4 — 50% tamaño nominal, 72 h sin alertas rojas, SLOs OK. Go ☐ / No-Go ☐

Notas: Cualquier incumplimiento → activar `emergency_stop`, registrar incidente, análisis causa raíz, repetir desde A.


