# PRD - GridBot

## Estado actual

- Sincronización automática de balances y límites de Binance al iniciar el sistema.
- Persistencia de operaciones, configuraciones y límites en PostgreSQL.
  - Estrategias implementadas: Grid, Scalping, Trailing Stop, RSI/MACD.
- Validación y ajuste automático de órdenes para cumplir con `step_size` y `min_notional` de Binance.
- Scheduler automático con APScheduler para ejecución periódica de estrategias.
- Logging robusto de eventos, errores y operaciones.
- Integración de alertas por Telegram (operaciones y errores críticos).
- Tests unitarios y de endpoints críticos.
- Dockerización completa (app + db + worker).

## Endpoints REST implementados

| Endpoint                | Método | Descripción                                                                                 |
|-------------------------|--------|--------------------------------------------------------------------------------------------|
| /order                  | POST   | Ejecuta una orden de compra/venta en Binance y la registra en la base de datos              |
| /run_grid               | POST   | Ejecuta la estrategia grid con los parámetros configurados                                  |
| /strategy/scalping      | POST   | Ejecuta la estrategia de scalping sobre un histórico de precios                             |
| /strategy/backtest      | POST   | Realiza backtesting de una estrategia (Grid, Scalping, Trailing Stop, RSI/MACD)             |
| /api/trade/balances     | GET    | Consulta de saldos en Binance                                                               |

## Pendientes / Próximos pasos

- Dashboard web para visualizar operaciones y métricas.
- Monitoreo avanzado (Prometheus/Grafana).
- Mejoras de seguridad y validación avanzada de parámetros.
- Paginación y filtros avanzados en `/trades`.
- Análisis de rendimiento y reportes.
- Documentación de endpoints y ejemplos de uso.
- Pruebas de integración y stress.
- Documentar ejemplos de uso y despliegue seguro en producción.

## Advertencia

Antes de operar con dinero real:
- Ejecutar todos los tests.
- Realizar pruebas de integración en modo paper trading o con cantidades mínimas.
- Revisar los logs y alertas de Telegram.
- Completar la integración de monitoreo avanzado (Prometheus/Grafana).

---

(El resto del documento mantiene la arquitectura, modelos y ejemplos ya presentes, solo se actualiza el estado y próximos pasos al inicio.)
