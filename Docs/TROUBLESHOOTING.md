# 🔧 Guía de Troubleshooting - GridBot v2.5

## 🚨 Problemas Críticos y Soluciones

### 1. Errores de Binance API

#### Error -1021: Timestamp out of sync
**Síntomas:**
- Alertas de `BinanceAPIErrorsSpike` en Telegram
- Errores masivos de API de Binance
- Sistema no puede ejecutar órdenes

**Causa:**
- Desincronización de zona horaria entre Docker y Binance
- Docker ejecutándose en UTC-3 mientras Binance espera UTC

**Solución:**
```bash
# 1. Configurar zona horaria UTC en docker-compose.yml
environment:
  - TZ=UTC

# 2. Reiniciar servicios
docker-compose restart api celery_worker

# 3. Verificar sincronización
docker-compose exec api date
curl -s "https://api.binance.com/api/v3/time" | jq '.serverTime'
```

#### Error -1013: Filter failure LOT_SIZE
**Síntomas:**
- Órdenes rechazadas por Binance
- Errores en logs del rebalanceador

**Causa:**
- Cantidades no redondeadas según step_size de Binance
- Validación insuficiente de filtros de trading

**Solución:**
```bash
# 1. Verificar filtros del símbolo
curl -s "https://api.binance.com/api/v3/exchangeInfo" | jq '.symbols[] | select(.symbol=="SPKUSDT") | .filters[] | select(.filterType=="LOT_SIZE")'

# 2. El sistema ya incluye validación automática en auto_rebalancer_v2.py
# 3. Verificar logs de validación
docker-compose logs --since 10m celery_worker | grep "LOT_SIZE"
```

#### Error -1111: Parameter quantity has too much precision
**Síntomas:**
- Órdenes rechazadas por demasiada precisión decimal
- Errores en rebalanceador

**Causa:**
- Cantidades con más decimales de los permitidos por Binance

**Solución:**
```bash
# 1. El sistema ya incluye redondeo automático
# 2. Verificar step_size del símbolo
# 3. Revisar logs de precisión
docker-compose logs --since 10m celery_worker | grep "precision"
```

### 2. Problemas de Métricas en Grafana

#### Panel 8 sin datos
**Síntomas:**
- Dashboard de Grafana muestra 0 en métricas de trading
- Panel 8 vacío o con datos incorrectos

**Causa:**
- Métricas no se están actualizando en Prometheus
- Valores en 0 en profit_total_usdt, roi_daily_percent

**Solución:**
```bash
# 1. Verificar métricas en Prometheus
curl -s 'http://localhost:9090/api/v1/query?query=profit_total_usdt' | jq

# 2. Actualizar métricas manualmente
docker-compose exec api python -c "
from app.core.metrics import profit_total_usdt, roi_daily_percent
profit_total_usdt.labels(strategy='grid').set(0.084)
roi_daily_percent.labels(strategy='grid').set(0.5)
print('✅ Métricas actualizadas')
"

# 3. Verificar actualización
curl -s 'http://localhost:9090/api/v1/query?query=profit_total_usdt' | jq
```

### 3. Problemas de Auto-Rebalancer V2

#### Rebalanceador no se activa
**Síntomas:**
- Liquidez baja pero rebalanceador no ejecuta
- Logs no muestran actividad de rebalanceo

**Causa:**
- Configuración incorrecta de umbrales
- Sistema en modo simulación

**Solución:**
```bash
# 1. Verificar configuración
grep -E "(MIN_USDT_BALANCE|TARGET_USDT_BALANCE|ENABLE_AUTO_REBALANCE)" .env

# 2. Verificar modo de trading
docker-compose exec api python -c "
import os
print(f'PAPER_TRADING: {os.getenv(\"PAPER_TRADING\")}')
print(f'FORCE_REAL_MODE: {os.getenv(\"FORCE_REAL_MODE\")}')
"

# 3. Activar rebalanceador manualmente
curl -X POST http://localhost:8000/api/rebalancer/check
```

#### Rebalanceador falla en ejecución
**Síntomas:**
- Errores de LOT_SIZE o precisión en rebalanceador
- Liquidación de activos fallida

**Causa:**
- Filtros de Binance no respetados
- Cantidades incorrectas

**Solución:**
```bash
# 1. Verificar logs detallados
docker-compose logs --since 5m celery_worker | grep -E "(rebalance|LOT_SIZE|precision)"

# 2. El sistema ya incluye validación automática
# 3. Verificar balances disponibles
curl -s http://localhost:8000/api/portfolio/summary | jq
```

### 4. Problemas de Circuit Breakers

#### Circuit breakers no funcionan
**Síntomas:**
- Pérdidas altas pero breakers no se activan
- Sistema continúa trading con pérdidas

**Causa:**
- Métricas de pérdidas no se están calculando
- Circuit breakers no configurados correctamente

**Solución:**
```bash
# 1. Verificar estado de breakers
curl -s http://localhost:8000/breakers/summary | jq

# 2. Verificar métricas de pérdidas
curl -s 'http://localhost:9090/api/v1/query?query=gridbot_profit_loss' | jq

# 3. Activar breakers manualmente si es necesario
curl -X POST http://localhost:8000/api/breakers/activate \
  -H "Content-Type: application/json" \
  -d '{"reason": "manual_activation", "threshold": 0.05}'
```

### 5. Problemas de Sincronización

#### API sigue en modo simulación
**Síntomas:**
- Variables de entorno configuradas pero API en simulación
- Trading no ejecuta órdenes reales

**Causa:**
- Variables de entorno del sistema sobrescriben .env
- Configuración de Docker no aplicada

**Solución:**
```bash
# 1. Verificar variables en contenedor
docker-compose exec api env | grep -E "(PAPER_TRADING|FORCE_REAL_MODE|BINANCE_TESTNET)"

# 2. Configurar explícitamente en docker-compose.yml
environment:
  - PAPER_TRADING=${PAPER_TRADING}
  - FORCE_REAL_MODE=${FORCE_REAL_MODE}
  - BINANCE_TESTNET=${BINANCE_TESTNET}

# 3. Reiniciar servicios
docker-compose restart api celery_worker
```

## 🔍 Comandos de Diagnóstico

### Verificar Estado del Sistema
```bash
# Estado general
docker-compose ps

# Logs de errores
docker-compose logs --since 1h | grep -E "(ERROR|Exception|Failed)"

# Métricas de Prometheus
curl -s 'http://localhost:9090/api/v1/query?query=up' | jq

# Estado de Binance
curl -s http://localhost:8000/api/portfolio/summary | jq
```

### Verificar Trading
```bash
# Verificar modo de trading
curl -s http://localhost:8000/health | jq

# Verificar balances
curl -s http://localhost:8000/api/reconciliation/summary | jq

# Verificar trades ejecutados
curl -s 'http://localhost:9090/api/v1/query?query=trades_executed_total' | jq
```

### Verificar Rebalanceador
```bash
# Estado del rebalanceador
curl -s http://localhost:8000/api/rebalancer/status | jq

# Ejecutar rebalanceo manual
curl -X POST http://localhost:8000/api/rebalancer/check

# Verificar logs
docker-compose logs --since 5m celery_worker | grep rebalance
```

## 🚨 Alertas y Monitoreo

### Alertas Críticas
- **BinanceAPIErrorsSpike**: Errores masivos de API
- **Liquidez baja**: USDT < 25
- **Circuit breakers**: Pérdidas > 5%
- **Discrepancia financiera**: > 1% o > 5 USDT

### Verificar Alertas
```bash
# Estado de alertas
curl -s 'http://localhost:9090/api/v1/alerts' | jq

# Métricas de errores
curl -s 'http://localhost:9090/api/v1/query?query=binance_api_errors_total' | jq

# Estado de liquidez
curl -s 'http://localhost:9090/api/v1/query?query=cash_balance_usdt' | jq
```

## 📞 Escalación de Problemas

### Nivel 1: Problemas Operativos
- Errores de API de Binance
- Métricas desactualizadas
- Rebalanceador no funciona

### Nivel 2: Problemas Críticos
- Circuit breakers no funcionan
- Pérdidas no controladas
- Sistema en modo simulación

### Nivel 3: Emergencia
- Pérdidas masivas
- Sistema no responde
- Datos corruptos

## 🔧 Scripts de Resolución Rápida

### Script de Verificación Completa
```bash
#!/bin/bash
echo "=== VERIFICACIÓN COMPLETA DEL SISTEMA ==="

# 1. Estado de servicios
echo "1. Estado de servicios:"
docker-compose ps

# 2. Verificar métricas
echo "2. Métricas de trading:"
curl -s 'http://localhost:9090/api/v1/query?query=profit_total_usdt' | jq

# 3. Verificar balances
echo "3. Balances:"
curl -s http://localhost:8000/api/portfolio/summary | jq

# 4. Verificar errores
echo "4. Errores recientes:"
docker-compose logs --since 10m | grep -E "(ERROR|Exception)" | tail -5

echo "=== VERIFICACIÓN COMPLETADA ==="
```

### Script de Corrección de Métricas
```bash
#!/bin/bash
echo "=== CORRIGIENDO MÉTRICAS ==="

# Actualizar métricas manualmente
docker-compose exec api python -c "
from app.core.metrics import profit_total_usdt, roi_daily_percent, profit_daily_usdt
profit_total_usdt.labels(strategy='grid').set(0.084)
roi_daily_percent.labels(strategy='grid').set(0.5)
profit_daily_usdt.labels(strategy='grid').set(0.084)
print('✅ Métricas actualizadas')
"

echo "=== CORRECCIÓN COMPLETADA ==="
```

## 📚 Referencias

- [FSD.md](FSD.md) - Especificaciones funcionales
- [PRD.md](PRD.md) - Requisitos del producto
- [README.md](README.md) - Documentación principal
- [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) - Guía de despliegue
