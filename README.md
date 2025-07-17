# GridBot

GridBot es una API de trading automatizado basada en FastAPI y PostgreSQL, diseñada para operar estrategias grid y otras (Scalping, Trailing Stop, RSI/MACD) en Binance. El proyecto está preparado para ejecutarse en contenedores Docker.

## Estructura del proyecto

```
grid_bot/
│
├── app/
│   ├── main.py          ← FastAPI app
│   ├── api/             ← Endpoints REST
│   ├── core/            ← Configuración, utils
│   ├── services/        ← Lógica de trading (Binance, grid, estrategias)
│   ├── models/          ← ORM con SQLAlchemy
│   ├── db/              ← Sesiones, migraciones
│   └── scheduler/       ← Jobs de trading
│
├── docker/
│   └── Dockerfile
│
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## Levantar el entorno de desarrollo

1. Copia el archivo `.env` con las variables de entorno necesarias.
2. Ejecuta:

```bash
docker-compose up --build
```

Esto levantará la API en `http://localhost:8000` y la base de datos PostgreSQL en el puerto `5432`.

## Roadmap
- [x] Setup base del proyecto
- [x] Modelos de datos y endpoints principales (`/order`, `/run_grid`, `/strategy/scalping`, `/strategy/backtest`)
- [x] Lógica de trading y conexión a Binance (incluye estrategias Grid, Scalping, Trailing Stop, RSI/MACD)
- [x] Scheduler y worker automático con APScheduler
- [ ] Dashboard web y alertas opcionales (Telegram, Prometheus/Grafana)
- [ ] Mejoras de seguridad, validación avanzada y documentación de endpoints
- [ ] Paginación y filtros avanzados en `/trades` 