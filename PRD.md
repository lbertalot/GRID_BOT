🏗️ Actualización del PRD con stack técnico nuevo

🔧 Stack Tecnológico
Componente	Tecnología elegida
API Backend	FastAPI ✅
Base de Datos	PostgreSQL (vía SQLAlchemy) ✅
Infraestructura	Docker (multi-servicio: app + db + worker) ✅
Trading	Binance Spot API vía SDK oficial ✅
Scheduler	APScheduler ✅
Alertas (opcional)	Telegram Bot (pendiente)
Monitoreo	Logs vía logging (básico) / Prometheus/Grafana (futuro)

🧱 Nueva Arquitectura del Sistema

                ┌─────────────────────┐
                │    Laptop Lenovo    │
                └────────┬────────────┘
                         │
             ┌───────────▼────────────┐
             │     Docker Compose     │
             └────┬──────────────┬────┘
                  │              │
        ┌─────────▼─────┐   ┌────▼────────┐
        │   FastAPI API │   │ PostgreSQL  │
        │ (gestión y UI)│   │ (histórico) │
        └───────────────┘   └─────────────┘
                  │
        ┌─────────▼─────────┐
        │ Bot Worker        │  ← Ejecuta lógica de trading
        │ (APScheduler)     │
        └───────────────────┘

🧩 Componentes del proyecto
📁 Estructura de carpetas real

```
grid_bot/
│
├── app/
│   ├── main.py          ← FastAPI app
│   ├── api/             ← Endpoints REST (trading, grid, consulta de operaciones)
│   ├── core/            ← Configuración, utils
│   ├── services/        ← Lógica de trading (Binance, grid, estrategias, logging de operaciones)
│   ├── models/          ← ORM con SQLAlchemy (Trade, GridConfig)
│   ├── db/              ← Sesiones, migraciones, init_db.py
│   └── scheduler/       ← Jobs de trading (APScheduler)
│
├── docker/
│   └── Dockerfile
│
├── docker-compose.yml
├── .env
├── requirements.txt
├── README.md
├── tests/               ← Tests automatizados (pytest)
└── PRD.md
```

✅ **Implementado**
- FastAPI app y estructura modular.
- Conexión y persistencia en PostgreSQL vía SQLAlchemy.
- Modelos ORM: operaciones (Trade) y configuración de grid (GridConfig).
- Endpoints REST principales:
  - `/order` (ejecutar orden y registrar en DB)
  - `/run_grid` (ejecutar estrategia grid)
  - `/strategy/scalping`, `/strategy/backtest` (estrategias y backtesting)
- Lógica de trading:
  - Estrategias implementadas: Grid, Scalping, Trailing Stop, RSI/MACD.
  - Cálculo de niveles de grid y toma de decisiones.
- Scheduler automático con APScheduler para grid trading.
- Logging básico de eventos y errores.
- Tests automatizados de estrategias y lógica base.
- Dockerización completa (app + db).

🚧 **Pendiente**
- Dashboard web para visualizar operaciones y métricas.
- Alertas/Notificaciones (Telegram Bot).
- Monitoreo avanzado (Prometheus/Grafana).
- Mejoras de seguridad y validación avanzada de parámetros.
- Paginación y filtros avanzados en `/trades`.
- Análisis de rendimiento y reportes.
- Documentación de endpoints y ejemplos de uso.

Binance 
BINANCE_API_KEY=tu_api_key
BINANCE_API_SECRET=tu_secret_key

---

## Endpoints REST implementados

| Endpoint                | Método | Descripción                                                                                 |
|-------------------------|--------|--------------------------------------------------------------------------------------------|
| /order                  | POST   | Ejecuta una orden de compra/venta en Binance y la registra en la base de datos              |
| /run_grid               | POST   | Ejecuta la estrategia grid con los parámetros configurados                                  |
| /strategy/scalping      | POST   | Ejecuta la estrategia de scalping sobre un histórico de precios                             |
| /strategy/backtest      | POST   | Realiza backtesting de una estrategia (Grid, Scalping, Trailing Stop, RSI/MACD)             |

### Pendientes/Futuros
| Endpoint                | Método | Descripción                                                                                 |
|-------------------------|--------|--------------------------------------------------------------------------------------------|
| /balances               | GET    | Consulta de saldos en Binance                                                               |
| /price/{symbol}         | GET    | Consulta el precio actual de un símbolo                                                     |
| /grid_config            | GET/POST| Consulta o actualiza la configuración de la estrategia grid                                 |
| /trades                 | GET    | Historial de operaciones, con filtros y paginación avanzada                                 |

---

## Ejemplos de uso de endpoints

### /order (POST)
**Request:**
```json
{
  "symbol": "BTCUSDT",
  "side": "BUY",
  "quantity": 0.01,
  "type": "MARKET"
}
```
**Response (éxito):**
```json
{
  "order": {
    "symbol": "BTCUSDT",
    "orderId": 123456,
    "status": "FILLED",
    ...
  }
}
```

### /run_grid (POST)
**Request:**
```json
{
  "symbol": "BTCUSDT",
  "min_price": 20000,
  "max_price": 30000,
  "grids": 5,
  "quantity": 0.01,
  "last_action": null
}
```
**Response (éxito):**
```json
{
  "decision": {"action": "BUY", "level": 2, ...},
  "order_result": {"symbol": "BTCUSDT", ...}
}
```

### /strategy/scalping (POST)
**Request:**
```json
{
  "symbol": "BTCUSDT",
  "interval": "1m",
  "limit": 10,
  "balances": {"USDT": 100},
  "params": {}
}
```
**Response (éxito):**
```json
{
  "action": "BUY",
  "details": {...}
}
```

### /strategy/backtest (POST)
**Request:**
```json
{
  "strategy": "scalping",
  "symbol": "BTCUSDT",
  "interval": "1h",
  "limit": 50,
  "balances": {"USDT": 100},
  "params": {}
}
```
**Response (éxito):**
```json
[
  {"step": 10, "price": 25000, "action": "BUY", ...},
  {"step": 11, "price": 25100, "action": "SELL", ...},
  ...
]
```

## Ejemplos propuestos para endpoints futuros

### /balances (GET)
**Response (éxito):**
```json
{
  "BTC": 0.05,
  "USDT": 1200.50,
  ...
}
```

### /price/{symbol} (GET)
**Response (éxito):**
```json
{
  "symbol": "BTCUSDT",
  "price": 29500.25
}
```

### /grid_config (GET)
**Response (éxito):**
```json
{
  "symbol": "BTCUSDT",
  "min_price": 20000,
  "max_price": 30000,
  "grids": 5,
  "quantity": 0.01,
  "last_action": "SELL"
}
```

### /grid_config (POST)
**Request:**
```json
{
  "symbol": "BTCUSDT",
  "min_price": 21000,
  "max_price": 31000,
  "grids": 6,
  "quantity": 0.02
}
```
**Response (éxito):**
```json
{
  "message": "Configuración actualizada",
  "config": { ... }
}
```

### /trades (GET)
**Request (con filtros):**
`/trades?symbol=BTCUSDT&side=BUY&limit=10&offset=0`

**Response (éxito):**
```json
{
  "total": 42,
  "results": [
    {
      "id": 1,
      "symbol": "BTCUSDT",
      "side": "BUY",
      "quantity": 0.01,
      "entry_price": 25000,
      "exit_price": 25500,
      "profit_loss": 5.0,
      "timestamp": "2024-06-01T12:00:00Z"
    },
    ...
  ]
}
```

## Modelos de datos principales

### Trade
| Campo        | Tipo     | Descripción                        |
|--------------|----------|------------------------------------|
| id           | int      | Identificador único                |
| symbol       | str      | Par de trading (ej: BTCUSDT)       |
| side         | str      | BUY o SELL                         |
| quantity     | float    | Cantidad operada                   |
| entry_price  | float    | Precio de entrada                  |
| exit_price   | float?   | Precio de salida (si aplica)       |
| profit_loss  | float?   | Ganancia/Pérdida (si aplica)       |
| timestamp    | datetime | Fecha/hora de la operación         |

### GridConfig
| Campo        | Tipo     | Descripción                        |
|--------------|----------|------------------------------------|
| id           | int      | Identificador único                |
| symbol       | str      | Par de trading (ej: BTCUSDT)       |
| min_price    | float    | Precio mínimo de la grilla         |
| max_price    | float    | Precio máximo de la grilla         |
| grids        | int      | Número de niveles de la grilla     |
| quantity     | float    | Cantidad por orden                 |
| last_action  | str?     | Última acción ejecutada            |

---

## Flujos de negocio principales

### 1. Ejecución de orden manual
- El usuario envía una orden vía `/order`.
- El sistema ejecuta la orden en Binance y la registra en la base de datos (`Trade`).

### 2. Ejecución de estrategia grid
- El usuario o el scheduler ejecuta `/run_grid`.
- Se calculan los niveles de la grilla y se consulta el precio actual.
- Se decide si ejecutar una orden (BUY/SELL) según la estrategia y el estado (`GridConfig`).
- Si se ejecuta una orden, se registra en la base de datos.

### 3. Backtesting de estrategias
- El usuario llama a `/strategy/backtest` con los parámetros deseados.
- El sistema simula la estrategia sobre un histórico de precios y devuelve los resultados paso a paso.

### 4. Scheduler automático
- Un job programado ejecuta periódicamente la estrategia grid usando los parámetros configurados.
- El resultado se registra y se actualiza el estado de la grilla.

---

## Dependencias técnicas

- **FastAPI**: Framework principal para la API REST.
- **SQLAlchemy**: ORM para la gestión de modelos y persistencia en PostgreSQL.
- **APScheduler**: Programador de tareas para la ejecución automática de estrategias.
- **python-binance**: SDK oficial para interactuar con la API de Binance.
- **Docker/Docker Compose**: Contenerización y orquestación de servicios (API, base de datos).
- **pytest**: Testing automatizado de lógica y endpoints.
- **Jinja2**: Renderizado de plantillas HTML (para la web mínima).
- **Prometheus/Grafana** (futuro): Monitoreo y métricas avanzadas.
- **Telegram Bot** (futuro): Alertas y notificaciones.

---
