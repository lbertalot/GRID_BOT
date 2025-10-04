# 📊 Guía de Monitoreo de GridBot

## 📋 **Tabla de Contenidos**

1. [Prometheus](#prometheus)
2. [Grafana](#grafana)
3. [Dashboards](#dashboards)
4. [Alertas](#alertas)
5. [Métricas Personalizadas](#métricas-personalizadas)
6. [Solución de Problemas](#solución-de-problemas)

---

## 🔍 **Prometheus**

### **Acceso:**
- **URL:** http://localhost:9090
- **Puerto:** 9090
- **Configuración:** `docker/prometheus.yml`

### **Métricas Principales:**

#### **GridBot Metrics:**
```
# Órdenes
gridbot_orders_total
gridbot_orders_failed_total
gridbot_volume_total

# Profit/Loss
gridbot_profit_loss_total
gridbot_profit_loss_percentage

# Estrategias
gridbot_strategies_active
gridbot_strategy_status

# Balances
gridbot_balance_total
gridbot_balance_by_asset
```

#### **Binance Metrics:**
```
# Conexión
binance_connection_status
binance_api_requests_total
binance_api_errors_total
binance_response_time

# Trading
binance_orders_total
binance_trades_total
binance_volume_total
```

#### **Sistema Metrics:**
```
# API
http_requests_total
http_request_duration_seconds
http_requests_failed_total

# Base de Datos
postgres_connections_active
postgres_queries_total
postgres_query_duration_seconds

# Recursos
process_cpu_seconds_total
process_resident_memory_bytes
```

### **Consultas Útiles:**

#### **Estado de Conexión:**
```promql
# Estado de conexión a Binance
binance_connection_status

# Errores de API
rate(binance_api_errors_total[5m])

# Tiempo de respuesta
histogram_quantile(0.95, rate(binance_response_time_bucket[5m]))
```

#### **Trading Performance:**
```promql
# Órdenes por minuto
rate(gridbot_orders_total[1m])

# Profit/Loss total
gridbot_profit_loss_total

# Volumen total
gridbot_volume_total
```

#### **Sistema:**
```promql
# CPU usage
rate(process_cpu_seconds_total[1m]) * 100

# Memory usage
process_resident_memory_bytes / 1024 / 1024

# API requests
rate(http_requests_total[1m])
```

---

## 📈 **Grafana**

### **Acceso:**
- **URL:** http://localhost:3000
- **Puerto:** 3000
- **Credenciales:**
  - Usuario: `admin`
  - Contraseña: `gridbot123`

### **Configuración Inicial:**

#### **1. Datasource:**
- **Tipo:** Prometheus
- **URL:** `http://prometheus:9090`
- **Access:** Server (default)

#### **2. Dashboards:**
- **GridBot Overview:** Dashboard principal
- **Trading Performance:** Métricas de trading
- **System Health:** Salud del sistema

### **Dashboard: GridBot Overview**

#### **Panel 1: Estado de Conexión**
```
Título: Binance Connection Status
Query: binance_connection_status
Visualización: Stat
```

#### **Panel 2: Órdenes por Minuto**
```
Título: Orders per Minute
Query: rate(gridbot_orders_total[1m])
Visualización: Time series
```

#### **Panel 3: Profit/Loss**
```
Título: Total P&L
Query: gridbot_profit_loss_total
Visualización: Stat
```

#### **Panel 4: Volumen Total**
```
Título: Total Volume
Query: gridbot_volume_total
Visualización: Stat
```

#### **Panel 5: Errores de API**
```
Título: API Errors
Query: rate(binance_api_errors_total[5m])
Visualización: Time series
```

#### **Panel 6: Balances por Asset**
```
Título: Balances by Asset
Query: gridbot_balance_by_asset
Visualización: Pie chart
```

---

## 🎯 **Dashboards**

### **Dashboard 1: GridBot Overview**
**Descripción:** Vista general del sistema

**Paneles:**
1. **Connection Status** - Estado de conexión a Binance
2. **Orders Rate** - Órdenes por minuto
3. **Total P&L** - Profit/Loss total
4. **Total Volume** - Volumen total
5. **API Errors** - Errores de API
6. **Active Strategies** - Estrategias activas
7. **System Resources** - CPU, Memory, Disk
8. **Database Health** - Estado de PostgreSQL

### **Dashboard 2: Trading Performance**
**Descripción:** Métricas específicas de trading

**Paneles:**
1. **Order Success Rate** - Tasa de éxito de órdenes
2. **Average Order Size** - Tamaño promedio de órdenes
3. **Profit/Loss by Strategy** - P&L por estrategia
4. **Volume by Symbol** - Volumen por símbolo
5. **Order Distribution** - Distribución de órdenes
6. **Trading Hours** - Horas de trading activo

### **Dashboard 3: System Health**
**Descripción:** Salud del sistema y infraestructura

**Paneles:**
1. **API Response Time** - Tiempo de respuesta de API
2. **Database Connections** - Conexiones a base de datos
3. **Memory Usage** - Uso de memoria
4. **CPU Usage** - Uso de CPU
5. **Disk Usage** - Uso de disco
6. **Network Traffic** - Tráfico de red

---

## 🚨 **Alertas**

### **Configuración de Alertas:**

#### **1. Alertas de Binance:**
```yaml
# Conexión perdida
- alert: BinanceConnectionLost
  expr: binance_connection_status == 0
  for: 1m
  labels:
    severity: critical
  annotations:
    summary: "Conexión a Binance perdida"
    description: "GridBot no puede conectarse a Binance"

# Errores de API
- alert: BinanceAPIErrors
  expr: rate(binance_api_errors_total[5m]) > 0.1
  for: 2m
  labels:
    severity: warning
  annotations:
    summary: "Errores de API de Binance"
    description: "Demasiados errores de API en los últimos 5 minutos"
```

#### **2. Alertas de Trading:**
```yaml
# Órdenes fallidas
- alert: HighOrderFailureRate
  expr: rate(gridbot_orders_failed_total[5m]) / rate(gridbot_orders_total[5m]) > 0.1
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "Alta tasa de fallos en órdenes"
    description: "Más del 10% de las órdenes están fallando"

# Pérdidas significativas
- alert: SignificantLosses
  expr: gridbot_profit_loss_total < -100
  for: 1m
  labels:
    severity: critical
  annotations:
    summary: "Pérdidas significativas detectadas"
    description: "GridBot ha perdido más de $100"
```

#### **3. Alertas de Sistema:**
```yaml
# Alto uso de CPU
- alert: HighCPUUsage
  expr: rate(process_cpu_seconds_total[1m]) * 100 > 80
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "Alto uso de CPU"
    description: "CPU usage está por encima del 80%"

# Alto uso de memoria
- alert: HighMemoryUsage
  expr: process_resident_memory_bytes / 1024 / 1024 > 2048
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "Alto uso de memoria"
    description: "Uso de memoria por encima de 2GB"
```

### **Configurar Alertas en Grafana:**

#### **1. Crear Canal de Notificación:**
1. Ve a **Alerting** → **Notification channels**
2. Haz clic en **Add channel**
3. Configura:
   - **Name:** GridBot Alerts
   - **Type:** Email/Telegram/Webhook
   - **Settings:** Configura según el tipo

#### **2. Crear Alertas:**
1. Ve a un panel
2. Haz clic en **Alert**
3. Configura:
   - **Condition:** Query y threshold
   - **Evaluation:** Intervalo de evaluación
   - **Notifications:** Canal configurado

---

## 📊 **Métricas Personalizadas**

### **Agregar Nuevas Métricas:**

#### **1. En el Código:**
```python
from app.core.metrics import (
    gridbot_orders_total,
    gridbot_profit_loss_total,
    gridbot_volume_total
)

# Registrar métrica
gridbot_orders_total.labels(
    symbol="BNBUSDT",
    side="BUY",
    strategy="grid"
).inc()

# Registrar profit/loss
gridbot_profit_loss_total.labels(
    symbol="BNBUSDT",
    strategy="grid"
).set(profit_loss_value)

# Registrar volumen
gridbot_volume_total.labels(
    symbol="BNBUSDT",
    side="BUY"
).inc(volume_amount)
```

#### **2. En Prometheus:**
```yaml
# Agregar a prometheus.yml
scrape_configs:
  - job_name: 'gridbot'
    static_configs:
      - targets: ['api:8000']
    metrics_path: '/api/metrics/metrics/'
```

#### **3. En Grafana:**
1. Crear nuevo panel
2. Usar query PromQL
3. Configurar visualización

---

## 🛠️ **Solución de Problemas**

### **Prometheus no recibe métricas:**

#### **Verificar Configuración:**
```bash
# Verificar configuración
docker-compose exec prometheus cat /etc/prometheus/prometheus.yml

# Verificar targets
curl http://localhost:9090/api/v1/targets

# Verificar métricas
curl http://localhost:8000/api/metrics/metrics/
```

#### **Solución:**
```bash
# Reiniciar Prometheus
docker-compose restart prometheus

# Verificar logs
docker-compose logs prometheus
```

### **Grafana no muestra datos:**

#### **Verificar Datasource:**
1. Ve a **Configuration** → **Data sources**
2. Verifica que Prometheus esté configurado
3. Test connection

#### **Verificar Queries:**
1. Ve a un panel
2. Edit query
3. Verifica sintaxis PromQL

### **Métricas no aparecen:**

#### **Verificar Endpoint:**
```bash
# Verificar métricas
curl http://localhost:8000/api/metrics/metrics/ | grep gridbot

# Verificar logs
docker-compose logs api | grep metrics
```

#### **Verificar Código:**
1. Verificar que las métricas estén registradas
2. Verificar que el endpoint esté configurado
3. Verificar logs de aplicación

---

## 📈 **Optimización**

### **Performance:**

#### **1. Retención de Datos:**
```yaml
# En prometheus.yml
storage:
  tsdb:
    retention.time: 30d  # 30 días
    retention.size: 10GB # 10GB máximo
```

#### **2. Scrape Interval:**
```yaml
# En prometheus.yml
global:
  scrape_interval: 15s  # Cada 15 segundos
  evaluation_interval: 15s
```

#### **3. Métricas Cardinalidad:**
- Limitar labels en métricas
- Usar relabeling para limpiar métricas
- Configurar recording rules

### **Almacenamiento:**

#### **1. Volúmenes Persistentes:**
```yaml
# En docker-compose.yml
volumes:
  prometheus_data:
    driver: local
  grafana_data:
    driver: local
```

#### **2. Backups:**
```bash
# Backup de Prometheus
docker-compose exec prometheus tar -czf /prometheus_data_backup.tar.gz /prometheus

# Backup de Grafana
docker-compose exec grafana tar -czf /grafana_data_backup.tar.gz /var/lib/grafana
```

---

## 📞 **Soporte**

### **Comandos Útiles:**
```bash
# Verificar Prometheus
curl http://localhost:9090/-/healthy

# Verificar Grafana
curl http://localhost:3000/api/health

# Ver métricas
curl http://localhost:8000/api/metrics/metrics/

# Ver logs
docker-compose logs prometheus
docker-compose logs grafana
```

### **Recursos:**
- **Prometheus Docs:** https://prometheus.io/docs/
- **Grafana Docs:** https://grafana.com/docs/
- **PromQL:** https://prometheus.io/docs/prometheus/latest/querying/

---

**🎉 ¡Monitoreo configurado correctamente!**

GridBot está siendo monitoreado con Prometheus y Grafana para máxima visibilidad y control.
