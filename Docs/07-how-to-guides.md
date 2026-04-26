## Guías Prácticas (How-to)

### Ejecutar un dry-run validado
```bash
make dry-run SYMBOL=BTCUSDT QTY=0.0002 SIDE=BUY TYPE=MARKET
```

### Forzar reconciliación y revisar resultados
```bash
curl -s http://localhost:8000/api/reconciliation/summary | jq
```

### Activar/Desactivar circuit breakers
```bash
curl -s http://localhost:8000/breakers/summary | jq
# Ejemplo activación crítica (si existe endpoint POST dedicado)
# curl -X POST http://localhost:8000/breakers/activate-critical
```

### Usar Auto-Rebalancer V2 manualmente
```bash
curl -X POST http://localhost:8000/api/rebalancer/check
curl -s http://localhost:8000/api/rebalancer/status | jq
```

### Ver y depurar métricas
```bash
curl -s http://localhost:8000/metrics | head -40
curl -s 'http://localhost:9090/api/v1/query?query=up' | jq
```
