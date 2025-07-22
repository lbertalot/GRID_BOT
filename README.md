# GridBot - Bot de Trading Automatizado

## 🚀 Descripción

GridBot es un sistema de trading automatizado que implementa estrategias de grid trading y otras (Scalping, Trailing Stop, RSI/MACD) sobre Binance Spot, usando FastAPI, PostgreSQL, SQLAlchemy y python-binance. El sistema es modular, dockerizado y seguro.

## 🏗️ Arquitectura

```
grid_bot/
├── app/
│   ├── api/           # Endpoints de la API (trading, grid, consulta de operaciones)
│   ├── core/          # Configuración, utilidades, lógica base
│   ├── db/            # Configuración y sesión de base de datos
│   ├── models/        # Modelos SQLAlchemy (Trade, GridConfig, AssetLimit)
│   ├── scheduler/     # Jobs programados (APScheduler)
│   ├── services/      # Lógica de trading (Binance, grid, estrategias, logging)
│   ├── schemas/       # Esquemas Pydantic
│   └── strategies/    # Estrategias de trading
├── scripts/           # Scripts de utilidad y automatización
├── docker/            # Configuración Docker, Prometheus, Grafana
├── tests/             # Tests unitarios y de integración
├── Docs/              # Documentación técnica y de despliegue
├── grid_config_optimized.json # Configuración de activos y grids
├── .env               # Variables de entorno (no versionado)
├── requirements.txt   # Dependencias
├── docker-compose.yml # Orquestación de servicios
└── README.md
```

## ⚙️ Tecnologías

- **Backend**: FastAPI, Python 3.11
- **Base de Datos**: PostgreSQL + SQLAlchemy + asyncpg
- **Trading**: python-binance
- **Scheduler**: APScheduler
- **Contenedores**: Docker & Docker Compose
- **Monitoreo**: Prometheus & Grafana (integración futura)
- **Alertas**: Telegram Bot (integrado)
- **Testing**: pytest, pytest-asyncio

## 🟢 Estado actual del desarrollo

- Sincronización automática de balances y límites de Binance al iniciar el sistema.
- Persistencia de operaciones, configuraciones y límites en PostgreSQL.
- Estrategias implementadas: Grid, Scalping, Trailing Stop, RSI/MACD.
- Validación y ajuste automático de órdenes para cumplir con `step_size` y `min_notional` de Binance.
- Scheduler automático con APScheduler para ejecución periódica de estrategias.
- Logging robusto de eventos, errores y operaciones.
- Integración de alertas por Telegram (operaciones y errores críticos).
- Tests unitarios y de endpoints críticos.
- Dockerización completa (app + db + worker).

## 🛠️ Instalación y despliegue

1. **Clonar el repositorio**
   ```bash
   git clone <repository-url>
   cd grid_bot
   ```
2. **Configurar variables de entorno**
   - Copia `.env.example` a `.env` y edítalo con tus credenciales de Binance y PostgreSQL.
3. **Ejecutar con Docker Compose**
   ```bash
   docker-compose up -d --build
   ```
4. **Ver logs**
   ```bash
   docker-compose logs -f api
   ```

## 📝 Configuración

- El archivo `grid_config_optimized.json` define los activos, cantidades, niveles de grid y rangos de precios.
- Los límites de trading (`min_notional`, `step_size`, etc.) se sincronizan automáticamente desde Binance y se usan para validar cada orden.

## 🔗 Endpoints REST principales

- `POST /order` - Ejecuta una orden de compra/venta y la registra en la base de datos
- `POST /run_grid` - Ejecuta la estrategia grid
- `POST /strategy/scalping` - Ejecuta la estrategia de scalping
- `POST /strategy/backtest` - Realiza backtesting de una estrategia
- `GET /api/trade/balances` - Consulta de saldos en Binance

## 🧪 Testing

```bash
pytest tests/
```

## 🚨 Seguridad y recomendaciones

- El sistema valida y ajusta automáticamente las órdenes para cumplir con las reglas de Binance.
- Las credenciales deben mantenerse seguras en `.env` (permisos 600).
- Antes de operar con dinero real, se recomienda:
  - Ejecutar todos los tests
  - Realizar pruebas de integración en modo paper trading o con cantidades mínimas
  - Revisar los logs y alertas de Telegram
  - Completar la integración de monitoreo avanzado (Prometheus/Grafana)

## 📈 Próximos pasos recomendados

- Mejorar el dashboard web para visualización de operaciones y métricas.
- Añadir monitoreo avanzado y alertas automáticas.
- Implementar paginación y filtros avanzados en `/trades`.
- Documentar ejemplos de uso y despliegue seguro en producción.
- Realizar pruebas de stress y edge cases.

## 📄 Licencia

MIT
