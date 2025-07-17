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
│   ├── services/        ← Lógica de trading (Binance, grid, logging de operaciones)
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
- Modelo de operaciones (Trade) y configuración de grid (GridConfig).
- Endpoints REST:
  - `/order` (ejecutar orden y registrar en DB)
  - `/balances` (consulta de saldos Binance)
  - `/price/{symbol}` (precio actual)
  - `/run_grid` (ejecutar estrategia grid)
  - `/grid_config` (consultar/actualizar config grid)
  - `/trades` (historial de operaciones, con filtros)
- Scheduler automático con APScheduler para grid trading.
- Logging básico de eventos y errores.
- Tests automatizados de imports, endpoints y lógica base.
- Dockerización completa (app + db).

🚧 **Pendiente**
- Dashboard web para visualizar operaciones y métricas.
- Alertas/Notificaciones (Telegram Bot).
- Monitoreo avanzado (Prometheus/Grafana).
- Estrategias adicionales (Trailing Stop, Scalping, RSI/MACD).
- Mejoras de seguridad y validación avanzada de parámetros.
- Paginación y filtros avanzados en `/trades`.
- Análisis de rendimiento y reportes.
- Documentación de endpoints y ejemplos de uso.

Binance 
BINANCE_API_KEY=tu_api_key
BINANCE_API_SECRET=tu_secret_key
