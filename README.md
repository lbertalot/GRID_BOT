# GridBot — Bot de Grid Trading Spot en Binance

[![CI / CD](https://github.com/lbertalot/GRID_BOT/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/lbertalot/GRID_BOT/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/lbertalot/GRID_BOT/branch/main/graph/badge.svg)](https://codecov.io/gh/lbertalot/GRID_BOT)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/release/python-3110/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**GridBot** es un sistema de trading algorítmico de grid trading spot para Binance, construido con FastAPI, Celery, Redis y PostgreSQL. Está diseñado para operar en **modo paper trading por defecto**, con validaciones estrictas y circuit breakers para protección de riesgo.

---

## ⚠️ Disclaimer

**Este software es solo para fines educativos e informativos. No constituye asesoramiento financiero. El trading con criptomonedas conlleva riesgos significativos. El modo de trading en vivo está desactivado por defecto y requiere configuración explícita.**

---

## 🚀 Características

- **Grid Trading Spot**: Estrategia de grid automatizada para Binance Spot
- **Paper Trading por defecto**: Opera en modo simulación sin riesgo
- **Gestión de riesgo**: Circuit breakers, límites de pérdida diaria, sizing adaptativo
- **Observabilidad**: Métricas Prometheus, dashboards Grafana, logs estructurados
- **Machine Learning opcional**: Motor híbrido con TensorFlow/Keras y River
- **API REST**: Endpoints para control y monitoreo
- **Celery workers**: Ejecución asíncrona de estrategias y tareas

---

## 📋 Requisitos

- Python 3.11+
- Docker y Docker Compose
- Cuenta de Binance (para API keys de testnet o producción)

---

## 🛠️ Instalación y Ejecución

### 1. Clonar el repositorio

```bash
git clone https://github.com/lbertalot/GRID_BOT.git
cd GRID_BOT
```

### 2. Configurar variables de entorno

Copia el archivo de ejemplo y edita con tus credenciales:

```bash
cp env.example .env
```

**Variables principales:**

```bash
# Credenciales de Binance (testnet o producción)
BINANCE_API_KEY=TU_API_KEY_AQUI
BINANCE_SECRET_KEY=TU_SECRET_KEY_AQUI

# Modo de operación (paper trading por defecto)
PAPER_TRADING=true
TRADING_ENABLED=false
EMERGENCY_STOP=false

# Base de datos y Redis (valores por defecto para Docker)
DATABASE_URL=postgresql://griduser:gridpass@db:5432/gridbot
REDIS_URL=redis://redis:6379

# Secret key para JWT (genera una clave segura)
SECRET_KEY=genera-una-clave-segura-con-openssl-rand-hex-32
```

### 3. Levantar los servicios con Docker Compose

**Entorno de desarrollo:**

```bash
docker compose --profile development up -d db redis
docker compose --profile development up -d api_dev
```

**Stack completo (incluye workers, Prometheus, Grafana):**

```bash
docker compose -f docker-compose.local.yml up --build -d
```

### 4. Verificar que la API está corriendo

```bash
curl http://localhost:8000/health
```

**Endpoints disponibles:**

- API: `http://localhost:8000`
- Documentación interactiva: `http://localhost:8000/docs`
- Métricas Prometheus: `http://localhost:8000/metrics`
- Grafana: `http://localhost:3000` (usuario/contraseña: `admin`/`admin`)
- Prometheus: `http://localhost:9090`
- Flower (Celery): `http://localhost:5555`

---

## 🧪 Ejecutar Tests

```bash
# Dentro del contenedor o en entorno local con dependencias instaladas
pytest -q

# Con reporte de cobertura
pytest --cov=app --cov-report=term-missing
```

---

## 📊 Monitoreo

El sistema incluye métricas Prometheus y dashboards Grafana preconfigurados:

- **Métricas de trading**: órdenes ejecutadas, PnL, ROI
- **Métricas de riesgo**: circuit breakers activos, drawdown
- **Métricas de sistema**: latencia API, errores, salud de servicios
- **Reconciliación**: estado de balance vs Binance

---

## 🔒 Seguridad y Trading en Vivo

**Por defecto, GridBot opera en modo paper trading (simulación).**

Para habilitar trading en vivo:

1. Configura credenciales reales de Binance con permisos de trading spot
2. Establece `PAPER_TRADING=false` y `TRADING_ENABLED=true` en `.env`
3. Revisa los límites de riesgo y circuit breakers
4. **Lee la documentación de seguridad en `AGENTS.md` y `Docs/`**

**⚠️ Nunca commitees claves API reales al repositorio.**

---

## 📚 Documentación

- **[AGENTS.md](AGENTS.md)**: Guía completa para desarrolladores y agentes
- **[Docs/](Docs/)**: Documentación técnica, runbooks y guías operativas
- **[env.example](env.example)**: Referencia de variables de entorno

---

## 🤝 Contribuciones

Las contribuciones son bienvenidas. Por favor:

1. Haz fork del repositorio
2. Crea una rama feature (`git checkout -b feature/nueva-funcionalidad`)
3. Realiza tus cambios con tests
4. Asegúrate de que los tests pasan (`pytest -q`)
5. Commitea con mensajes descriptivos (Conventional Commits)
6. Abre un Pull Request

---

## 📄 Licencia

Este proyecto está licenciado bajo la [Licencia MIT](LICENSE).

---

## 📧 Contacto

Para preguntas o soporte, abre un issue en GitHub.
