🏗️ Actualización del PRD con stack técnico nuevo
🔧 Stack Tecnológico
Componente	Tecnología elegida
API Backend	FastAPI
Base de Datos	PostgreSQL (vía SQLAlchemy o Tortoise ORM)
Infraestructura	Docker (multi-servicio: app + db + worker)
Trading	Binance Spot API vía SDK oficial
Scheduler	APScheduler o Celery (según complejidad)
Alertas (opcional)	Telegram Bot
Monitoreo	Logs vía logging o Prometheus/Grafana (futuro)

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
        │ (schedule/celery) │
        └───────────────────┘
🧩 Componentes del proyecto
📁 Estructura de carpetas propuesta
css
Copiar
Editar
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
│   ├── Dockerfile
│   └── docker-compose.yml
│
├── .env
├── requirements.txt
└── README.md
⚙️ Servicios Docker
docker-compose.yml básico
yaml
Copiar
Editar
version: '3.8'

services:
  db:
    image: postgres:16
    container_name: gridbot_db
    restart: always
    environment:
      POSTGRES_USER: griduser
      POSTGRES_PASSWORD: gridpass
      POSTGRES_DB: gridbot
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  api:
    build: ./docker
    container_name: gridbot_api
    ports:
      - "8000:8000"
    depends_on:
      - db
    env_file:
      - .env
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

volumes:
  pgdata:
🚀 Roadmap del desarrollo
Fase	Tarea	Entregable
1	Setup base del proyecto	FastAPI app + conexión DB + endpoints iniciales
2	Modelo de datos	SQLAlchemy models para operaciones, órdenes, logs
3	Bot simulador	Servicio que corre un grid virtual y registra resultados
4	Conexión Binance	API trading con claves seguras
5	Scheduler	Ejecución automática del bot en intervalos definidos
6	Dashboard (opcional)	Ver operaciones, ganancias, logs
7	Telegram Bot (opcional)	Notificaciones por operación / alertas

Binance 
BINANCE_API_KEY=tu_api_key
BINANCE_API_SECRET=tu_secret_key
