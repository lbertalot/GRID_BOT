# Guía de Reseteo de Métricas de Prometheus - GridBot v2.5

## ⚠️ ADVERTENCIA
Este procedimiento eliminará TODAS las métricas históricas de Prometheus. Es un proceso DESTRUCTIVO que no se puede deshacer.

## Objetivo
Resetear completamente las métricas de Prometheus para empezar con un estado limpio en producción.

## Procedimiento

### Paso 1: Detener Servicios
```bash
# Detener todos los servicios de GridBot
docker-compose down

# Verificar que todos los contenedores están detenidos
docker ps | grep gridbot
```

### Paso 2: Eliminar Datos de Prometheus
```bash
# Eliminar directorio de datos de Prometheus
sudo rm -rf ./docker/prometheus/data/*

# Verificar que el directorio está vacío
ls -la ./docker/prometheus/data/
```

### Paso 3: Limpiar Métricas de Redis (si aplica)
```bash
# Conectar a Redis y limpiar métricas
docker run --rm -it --network grid_bot_default redis:7-alpine redis-cli -h gridbot_redis

# Dentro de Redis CLI:
FLUSHDB
EXIT
```

### Paso 4: Reiniciar Servicios
```bash
# Iniciar servicios con datos limpios
docker-compose up -d --build

# Verificar que Prometheus está funcionando
curl -s http://localhost:9090/api/v1/query?query=up | jq .
```

### Paso 5: Verificar Reseteo Exitoso
```bash
# Verificar que no hay métricas históricas
curl -s "http://localhost:9090/api/v1/query?query=gridbot_trades_executed_total" | jq .

# Debería retornar: {"status":"success","data":{"resultType":"vector","result":[]}}
```

## Validación Post-Reseteo

### Métricas que deben estar en CERO:
- `gridbot_trades_executed_total`
- `gridbot_profit_loss`
- `gridbot_orders_created_total`
- `gridbot_api_requests_total`

### Métricas que deben estar en UNO (inicialización):
- `gridbot_system_uptime_seconds` (debe empezar desde 0)

## Comandos de Verificación Rápida

```bash
# Verificar estado de Prometheus
curl -s http://localhost:9090/api/v1/status/config | jq .data.yaml

# Verificar métricas específicas de GridBot
curl -s "http://localhost:9090/api/v1/query?query={__name__=~\"gridbot_.*\"}" | jq '.data.result | length'

# Debería retornar 0 o muy pocas métricas (solo las de inicialización)
```

## Troubleshooting

### Si Prometheus no inicia:
```bash
# Verificar logs
docker logs gridbot_prometheus

# Verificar permisos del directorio
ls -la ./docker/prometheus/data/
sudo chown -R 65534:65534 ./docker/prometheus/data/
```

### Si las métricas persisten:
```bash
# Forzar recreación del volumen
docker-compose down -v
docker volume prune -f
docker-compose up -d --build
```

## Notas Importantes

1. **Backup**: Si necesitas preservar métricas históricas, haz backup antes del reseteo:
   ```bash
   cp -r ./docker/prometheus/data ./docker/prometheus/data_backup_$(date +%Y%m%d_%H%M%S)
   ```
2. **Grafana**: Los dashboards de Grafana se resetearán automáticamente al no encontrar datos históricos.
3. **Alertas**: Las reglas de alertas se mantienen, pero no habrá datos históricos para evaluar.

## Estado Esperado Post-Reseteo

- ✅ Prometheus funcionando sin métricas históricas
- ✅ Grafana conectado a Prometheus limpio  
- ✅ Alertmanager funcionando con reglas activas
- ✅ Todas las métricas de GridBot en estado inicial
- ✅ Sistema listo para métricas de producción

---

**Fecha de creación:** 2025-09-18  
**Versión:** GridBot v2.5 Production Reset  
**Autor:** SRE Team
