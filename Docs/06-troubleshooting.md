## Guía de Solución de Problemas

### Errores de API de Binance

#### -1021: Timestamp out of sync
Síntomas: alertas de errores masivos, órdenes fallidas.

Solución:
```bash
# Forzar TZ=UTC en docker-compose.yml y reiniciar
docker-compose restart api celery_worker
docker-compose exec api date
curl -s "https://api.binance.com/api/v3/time" | jq '.serverTime'
```

#### -1013: Filter failure LOT_SIZE
Síntomas: órdenes rechazadas por step_size.

Solución:
```bash
curl -s "https://api.binance.com/api/v3/exchangeInfo" \
 | jq '.symbols[] | select(.symbol=="SPKUSDT") | .filters[] | select(.filterType=="LOT_SIZE")'
docker-compose logs --since 10m celery_worker | grep "LOT_SIZE"
```

#### -1111: Quantity con demasiada precisión
Síntomas: exceso de decimales.

Solución:
```bash
docker-compose logs --since 10m celery_worker | grep precision
```

### Problemas de Métricas (Grafana/Prometheus)

Panel sin datos o valores en 0:
```bash
curl -s 'http://localhost:9090/api/v1/query?query=profit_total_usdt' | jq
docker-compose exec api python -c "from app.core.metrics import profit_total_usdt; profit_total_usdt.labels(strategy='grid').set(0.084)"
```

### Auto-Rebalancer V2

No se activa:
```bash
grep -E "(MIN_USDT_BALANCE|TARGET_USDT_BALANCE|ENABLE_AUTO_REBALANCE)" .env
docker-compose exec api python - <<'PY'
import os; print(os.getenv('PAPER_TRADING')), print(os.getenv('FORCE_REAL_MODE'))
PY
curl -X POST http://localhost:8000/api/rebalancer/check
```

### Circuit Breakers

No responden:
```bash
curl -s http://localhost:8000/breakers/summary | jq
curl -s 'http://localhost:9090/api/v1/query?query=gridbot_profit_loss' | jq
```

### Sincronización y Modos

API permanece en simulación:
```bash
docker-compose exec api env | grep -E "(PAPER_TRADING|FORCE_REAL_MODE|BINANCE_TESTNET)"
docker-compose restart api celery_worker
```

### Diagnóstico Rápido
```bash
docker-compose ps
docker-compose logs --since 1h | grep -E "(ERROR|Exception|Failed)"
curl -s 'http://localhost:9090/api/v1/query?query=up' | jq
curl -s http://localhost:8000/api/portfolio/summary | jq
```


