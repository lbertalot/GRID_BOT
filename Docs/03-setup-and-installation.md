## Configuración del Entorno Local

### Prerrequisitos
- Docker y Docker Compose
- Git
- Opcional (sin Docker): Python 3.11+

### Instalación
```bash
git clone https://github.com/ORG/REPO.git
cd REPO
cp env.example .env
```

Edita `.env` con tus valores. Claves críticas:
```
BINANCE_API_KEY=...
BINANCE_SECRET_KEY=...
PAPER_TRADING=true
BINANCE_TESTNET=false
FORCE_REAL_MODE=false
TRADING_ENABLED=true
EMERGENCY_STOP=false
DATABASE_URL=postgresql://griduser:gridpass@db:5432/gridbot
REDIS_URL=redis://redis:6379
TZ=UTC
```

### Levantar el Entorno
```bash
docker compose --profile production up -d db redis prometheus grafana api
# Desarrollo (hot reload)
docker compose --profile development up -d db redis
docker compose --profile development up -d api_dev
```

### Verificación
```bash
# API health
curl -s http://localhost:8000/health | jq

# Métricas (Prometheus exposition)
curl -s http://localhost:8000/metrics | head -20

# Servicios en docker
docker compose ps
```

### Logs y Diagnóstico
```bash
# Tailing centralizado
make logs-tail-start

# Logs por servicio
docker compose logs -f api
docker compose logs -f celery_worker
```

### Simulación (Dry-Run)
```bash
make dry-run SYMBOL=BTCUSDT QTY=0.0002 SIDE=BUY TYPE=MARKET
```
