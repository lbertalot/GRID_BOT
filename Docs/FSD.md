# ⚙️ Functional Specification Document (FSD/TRS) – Trading Backend

## 1. Objetivo y Alcance
Definir especificaciones técnicas del backend de trading para ejecución segura y aprendizaje online.

## 2. Arquitectura General
- **Frontend/API**: FastAPI asíncrono.
- **ML Engine**: LSTM/Transformer + River.
- **Workers**: Celery + Redis.
- **DB**: PostgreSQL + SQLAlchemy.
- **Observabilidad**: Prometheus/Grafana.
- **Infraestructura**: Docker Compose/K8s.

### 2.1 Diagramas UML (referencias)
- Componentes: `docs/architecture.png`.
- Secuencia (orden E2E): `docs/seq_order.png`.
- DFD Emergencia/Breakers: `docs/dfd_emergency.png`.

## 3. Modelos de Datos
- ERD del esquema PostgreSQL (`docs/erd.png`).
- Contratos Pydantic para requests/responses.

### 3.1 Esquema de datos (resumen)
- Trades: id, symbol, side, qty, entry_price, exit_price, profit_loss, timestamps.
- System settings: claves/valores para baseline y configuraciones.
- Alerts/metrics snapshots (persistencia opcional según retención).

## 4. APIs y Contratos
- OpenAPI spec: [`openapi.json`](openapi.json)
 - OpenAPI spec: [`openapi.json`](openapi.json) — generado por CI en `Docs/openapi.json`.
- Endpoints:
  - `POST /orders`: crea orden → valida PRICE_FILTER, LOT_SIZE.
  - `GET /positions`: estado de posiciones.
  - `GET /breakers/summary`: estado de breakers.
  - `GET /api/reconciliation/summary`: `cash_usdt`, `portfolio_total_usdt`.
  - `POST /api/simulations/dry-run`: preflight validado (PAPER).

### 4.1 Contratos de datos (ejemplos)
Request `POST /api/simulations/dry-run`:
```json
{
  "symbol": "BTCUSDT",
  "side": "BUY",
  "order_type": "MARKET",
  "quantity": 0.0002
}
```

Response (200):
```json
{
  "status": "ok",
  "validated": true,
  "fees": 0.01,
  "notional": 10.5
}
```

## 5. Flujos Principales
- **Ejecución de Orden E2E**: [Diagrama de Secuencia](docs/seq_order.png).
- **Modo Emergencia / Circuit Breaker**: [Flujo DFD](docs/dfd_emergency.png).

Resumen del flujo de orden:
1) Validación: precisión (precio/cantidad), LOT_SIZE, PRICE_FILTER, MIN_NOTIONAL, balance suficiente.
2) Cálculo de tamaño: Kelly fraccional con límites.
3) Envío asíncrono a exchange; manejo de idempotencia y estados.
4) Tracking de fills parciales/errores y métricas.
5) Reconciliación periódica y auditoría.

## 6. Requisitos No Funcionales
| Categoría    | Requisito                       |
|---------------|-------------------------------|
| Rendimiento   | Latencia P99 ≤ 250 ms          |
| Escalabilidad | Horizontal en K8s              |
| Seguridad     | API keys en Vault, TLS 1.3     |
| Observabilidad| Métricas Prometheus + alertas   |

Detalles adicionales:
- Reconciliación ≤ 60 s; colas asíncronas para I/O externo.
- Idempotencia por `client_order_id` y exactamente-una-vez en tracking a nivel app.
- Logs estructurados con correlación por orden.

## 7. Dependencias Externas
- Binance API.
- Redis Cluster.
- PostgreSQL 14+.
- Docker ≥ 24.

## 8. Casos de Prueba Iniciales
- Validación PRICE_FILTER/LOT_SIZE/MIN_NOTIONAL y balance suficiente.
- Reconciliación detectando discrepancias y publicando métricas.
- Fallback de modelos ML y continuidad operativa.
- Pruebas de latencia y P99 API.

## 9. Riesgos Técnicos
- Fallo en River online learning → fallback a modelo LSTM estático.
- Desincronización WS/API → reconciliación determinística y reintentos con backoff.
- Errores de precisión → normalizador de cantidades/precios y caché `exchange_info`.
