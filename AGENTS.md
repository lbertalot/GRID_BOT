## GridBot v2.5 — Guía para Agentes (Coding Agents) y Colaboradores

### Objetivo del documento
Este archivo acelera el onboarding de agentes y nuevos colaboradores. Resume cómo construir, probar, desplegar y contribuir al proyecto, con énfasis en seguridad, integridad financiera y observabilidad.

---

## Visión general del proyecto
- **Stack principal**: FastAPI (API), Celery (workers), Redis (broker/cache), PostgreSQL (persistencia), Prometheus/Grafana (observabilidad).
- **Dominio**: Trading algorítmico spot en Binance con defensas estrictas, sizing adaptativo (Kelly fraccional) y reconciliación periódica.
- **Principios clave**:
  - Defensa y seguridad primero (PRICE_FILTER, LOT_SIZE, MIN_NOTIONAL; breakers; idempotencia).
  - Observabilidad total (métricas Prometheus, logs estructurados, dashboards Grafana).
  - Integridad financiera (Decimal para precios/cantidades, reconciliación ≤ 60s).
  - Inteligencia adaptativa (ML con fallback seguro).
  - Rendimiento asíncrono (I/O non-blocking, P99 ≤ 250 ms).

### Estructura relevante
- `app/api/`: routers/endpoints (FastAPI)
- `app/services/`: lógica de negocio (validación, sizers, reconciliación, métricas, Binance, etc.)
- `app/core/`: configuración, métricas, middleware, auth, circuit breakers, celery app
- `app/models` y `app/schemas`: modelos de BD y Pydantic v2 para I/O
- `docker/`: infra local (Prometheus, Grafana, Nginx, Postgres)
- `tests/`: suite de pruebas (API, trading, integración, métricas, ML)
- `Docs/` y `PRODUCTION_LAUNCH_GUIDE.md`: documentación y guía de despliegue

---

## Requisitos y entorno
- Python 3.11+
- Docker y Docker Compose
- Archivo `.env` (basado en `env.example` o `19092025.env`/`production.env` según tu flujo)

Variables de entorno críticas: `BINANCE_API_KEY`, `BINANCE_SECRET_KEY`, `PAPER_TRADING`, `FORCE_REAL_MODE`, `TRADING_ENABLED`, `EMERGENCY_STOP`, `DATABASE_URL`, `REDIS_URL`.

---

## Comandos de build y ejecución

### Desarrollo (hot-reload)
```bash
docker compose --profile development up -d db redis
docker compose --profile development up -d api_dev
# API en http://localhost:8000
```

### Producción local
```bash
docker compose --profile production up -d db redis prometheus grafana api
# Salud: http://localhost:8000/health
# Métricas: http://localhost:8000/metrics
# Prometheus: http://localhost:9090
# Grafana: http://localhost:3000
```

### Stack completo local (`docker-compose.local.yml`)
Incluye API, Celery worker/beat, Flower, Postgres, Redis, Prometheus, Grafana, exporters y cAdvisor. Requiere `.env` en la raíz del repo.

```bash
docker compose -f docker-compose.local.yml up --build -d
```

- API: `http://localhost:8000` · Flower: `5555` · Grafana: `3000` · Prometheus: `9090` · cAdvisor: `8081`
- Flower usa Basic Auth desde `FLOWER_BASIC_AUTH_*`; en desarrollo local se puede poner `FLOWER_DISABLE_AUTH=1` en `.env` para desactivar la autenticación.

### Uvicorn local (sin Docker)
```bash
uvicorn app.main:app --reload --port 8000
```

### Celery (workers/beat) con Docker
```bash
docker compose up -d celery_worker celery_beat
```

### Utilidades (Makefile)
```bash
# Simulación PAPER para validar filtros/notional sin enviar órdenes reales
make dry-run SYMBOL=BTCUSDT QTY=0.0002 SIDE=BUY TYPE=MARKET

# Tail de logs de contenedores a logs/dockers.log
make logs-tail-start
```

---

## Estilo de código y convenciones
- **Funcional y declarativo**: prioriza funciones puras; evita clases salvo necesidad.
- **Async I/O**: usa `async def` para llamadas externas (DB, Redis, Binance, HTTP).
- **Tipado estricto**: anota todas las firmas; usa Pydantic v2 para inputs/outputs.
- **RORO** (Receive an Object, Return an Object): recibe/retorna objetos tipados.
- **Moneda y precios**: emplea `Decimal` para evitar errores de punto flotante.
- **Validación temprana**: guard clauses y early returns para errores/edge cases.
- **FastAPI**: dependencia explícita, middlewares para logging/errores/Prometheus.
- **Rutas**: define rutas y esquemas en `app/api/` y `app/schemas/` respectivamente.
- **Servicios**: coloca la lógica en `app/services/`, modular y testeable.

Al añadir endpoints/servicios:
- Valida contra `exchange_info` (PRICE_FILTER, LOT_SIZE, MIN_NOTIONAL) y balance.
- Consulta breakers antes de ejecutar operaciones críticas.
- Instrumenta métricas Prometheus (counters/gauges/histograms) y logs JSON.
- Usa `client_order_id` para idempotencia con el exchange.

---

## Pruebas y cobertura
```bash
# Instalar deps si corres fuera de Docker
python -m pip install -r requirements.txt

# Ejecutar toda la suite
pytest -q

# Cobertura
pytest --cov=app --cov-report=term-missing

# Ejecutar un test específico
pytest tests/test_trading_cycle.py::test_trading_cycle_tick -q
```

Recomendaciones:
- Usa `PAPER_TRADING=true` y/o `BINANCE_TESTNET=true` en entorno de prueba.
- Evita llamadas reales a Binance en tests; usa fixtures/doubles donde existan.
- Mantén cobertura > 85% en módulos críticos (validadores, sizers, reconciliación, breakers, middleware).

---

## Seguridad y consideraciones críticas
- Nunca versiones claves reales; usa `.env` y variables de CI.
- Habilita breakers y límites de riesgo; valida `TRADING_ENABLED`/`EMERGENCY_STOP`.
- Verifica parámetros de órdenes contra filtros del exchange antes de enviar.
- Calcula sizing con `Decimal` y límites duros; aplica Kelly fraccional con topes.
- Asegura idempotencia de órdenes con `client_order_id`.
- Logs estructurados con `trace_id`/`order_id`; no loguees secretos.
- Fallback para modelos ML si fallan o son no confiables.

---

## Observabilidad
- Endpoint de métricas: `GET /metrics` (Prometheus text format).
- Dashboards: importa `grafana-roi-dashboard.json` en Grafana.
- Métricas clave (ejemplos): órdenes validadas/ejecutadas, breakers activos, PnL, latencia E2E.
- Consulta `PRODUCTION_LAUNCH_GUIDE.md` para queries y alertas recomendadas.

---

## Despliegue
Pasos resumidos (ver `PRODUCTION_LAUNCH_GUIDE.md` para detalle y checklist):
```bash
cp production.env .env   # Ajusta credenciales reales con permisos spot
./launch.sh              # Orquesta servicios, healthchecks y logs
./setup-monitoring.sh    # Configura Prometheus/Grafana/Alertmanager
```

URLs locales:
- API: `http://localhost:8000`
- Health: `http://localhost:8000/health`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`

---

## Pautas de commits y PRs

### Convenciones de commit (Conventional Commits)
- `feat: ...` nueva funcionalidad
- `fix: ...` corrección de bug
- `docs: ...` documentación
- `refactor: ...` refactor sin cambios funcionales
- `test: ...` tests
- `chore: ...` tareas varias (build/devops)

Incluye contexto breve y el impacto observable (métricas, endpoints, riesgos).

### Checklist para PRs
- [ ] Tests pasan en CI/local y cobertura adecuada
- [ ] Sin secretos ni datos sensibles en commits/logs
- [ ] Rutas validadas con guard clauses y `Decimal` en cálculos
- [ ] Métricas Prometheus añadidas/actualizadas y dashboards revisados
- [ ] Documentación actualizada (`Docs/`, este `AGENTS.md` si aplica)
- [ ] Considerado breaker/idempotencia/rollback en operaciones críticas

---

## Datos y artefactos grandes
- Coloca datasets en `data/` (ignora archivos pesados en .git si corresponde).
- No incluyas modelos binarios grandes en el repo; versiona artefactos vía releases o almacenamiento externo.
- Para ML en vivo (River/TensorFlow), implementa carga perezosa y fallback.

---

## Dónde tocar el código (mapa rápido para agentes)
- Nuevas rutas HTTP: `app/api/` (exporta `router` y usa Pydantic v2 para I/O)
- Lógica de negocio: `app/services/` (funciones puras; modulariza por dominio)
- Tipos/esquemas: `app/schemas/` y `app/models/`
- Métricas/observabilidad: `app/core/metrics.py`, `app/core/middleware/`
- Tareas asíncronas: `app/core/celery_app.py` y workers en `app/services/`/`workers/`

Consejo: evita lógica bloqueante en rutas; delega a Celery lo intensivo o de larga duración.

---

## Troubleshooting rápido
```bash
# Logs de un servicio
docker compose logs -f api

# Health básico
curl http://localhost:8000/health

# Validar endpoints de integridad y breakers
curl http://localhost:8000/breakers/summary
curl http://localhost:8000/integrity/status
```

---

## Contacto y soporte
- Alertas por Telegram (configura `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID`).
- Revisa `logs/` y `reports/` para auditorías y monitoreo continuo.


