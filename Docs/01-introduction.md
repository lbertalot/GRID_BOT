## Introducción a GridBot v2.5

### ¿Qué es GridBot v2.5?
GridBot v2.5 es un backend de trading algorítmico para Binance orientado a bajo riesgo, alta observabilidad y ejecución fiable. Combina una API asíncrona en FastAPI, workers Celery para tareas intensivas, un motor ML híbrido (River + Deep Learning) para detectar el régimen de mercado, y un conjunto de defensas por diseño: validación estricta de órdenes (PRICE_FILTER, LOT_SIZE, MIN_NOTIONAL, precisión), breakers y reconciliación financiera determinística (≤ 60 s).

### ¿Qué problema resuelve?
Basado en el PRD, GridBot v2.5 minimiza rechazos del exchange, pérdidas por errores de precisión y decisiones basadas en datos inconsistentes. Sus objetivos de negocio son:
- Latencia P99 ≤ 250 ms, uptime ≥ 99.9% y reconciliación ≤ 60 s.
- Rentabilidad con control de riesgo, aplicando Kelly fraccional con límites.
- Observabilidad 360°: métricas Prometheus, dashboards Grafana, alertas.
- Robustez operativa: circuit breakers multinivel y auditoría completa de órdenes.

### Stack Tecnológico Principal
- FastAPI (API asíncrona) y Uvicorn
- Celery + Redis (tareas asíncronas y broker/cache)
- PostgreSQL + SQLAlchemy 2.0 + Alembic (persistencia y migraciones)
- Prometheus + Grafana (métricas y visualización)
- Binance API + websockets
- ML: River (online), TensorFlow/Keras (LSTM/Transformer), vectorbt (backtesting)
