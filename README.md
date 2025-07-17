# GridBot

GridBot es una API de trading automatizado basada en FastAPI y PostgreSQL, diseñada para operar estrategias grid en Binance. El proyecto está preparado para ejecutarse en contenedores Docker.

## Estructura del proyecto

```
grid_bot/
│
├── app/
│   ├── main.py          ← FastAPI app
│   ├── api/             ← Endpoints REST
│   ├── core/            ← Configuración, utils
│   ├── services/        ← Lógica de trading (Binance)
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
- [ ] Modelos de datos y endpoints
- [ ] Lógica de trading y conexión a Binance
- [ ] Scheduler y worker
- [ ] Dashboard y alertas opcionales 