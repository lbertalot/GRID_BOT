# ⚡ Comandos Rápidos de GridBot

## 🚀 **Inicio Rápido**

### **Desplegar GridBot**
```bash
# Clonar repositorio
git clone https://github.com/tu-usuario/grid_bot.git
cd grid_bot

# Configurar variables
cp .env.example .env
nano .env

# Desplegar
docker-compose up -d

# Verificar estado
docker-compose ps
```

### **Verificar Instalación**
```bash
# Verificar API
curl http://localhost:8000/docs

# Verificar Prometheus
curl http://localhost:9090/-/healthy

# Verificar Grafana
curl http://localhost:3000/api/health
```

---

## 🔍 **Diagnóstico**

### **Verificar Credenciales de Binance**
```bash
# Verificación básica
docker-compose exec api python3 verify_binance_credentials.py

# Verificación detallada
docker-compose exec api python3 check_api_key_status.py

# Verificar IP
curl ifconfig.me
```

### **Verificar Estado de Servicios**
```bash
# Estado de todos los servicios
docker-compose ps

# Logs de API
docker-compose logs api

# Logs de base de datos
docker-compose logs db

# Logs de Prometheus
docker-compose logs prometheus

# Logs de Grafana
docker-compose logs grafana
```

### **Verificar Métricas**
```bash
# Métricas de Prometheus
curl http://localhost:8000/api/metrics/metrics/

# Métricas específicas
curl http://localhost:8000/api/metrics/metrics/ | grep gridbot

# Estado de salud
curl http://localhost:8000/api/metrics/metrics/health
```

---

## 🔧 **Mantenimiento**

### **Reiniciar Servicios**
```bash
# Reiniciar API
docker-compose restart api

# Reiniciar base de datos
docker-compose restart db

# Reiniciar monitoreo
docker-compose restart prometheus grafana

# Reiniciar todo
docker-compose restart
```

### **Actualizar GridBot**
```bash
# Actualizar código
git pull origin main

# Reconstruir contenedores
docker-compose down
docker-compose up -d --build

# Verificar actualización
docker-compose ps
```

### **Backups**
```bash
# Backup de base de datos
docker-compose exec db pg_dump -U griduser gridbot > backup_$(date +%Y%m%d).sql

# Backup de configuración
cp .env backup_env_$(date +%Y%m%d)

# Backup de volúmenes
docker run --rm -v grid_bot_pgdata:/data -v $(pwd):/backup alpine tar -czf /backup/pgdata_$(date +%Y%m%d).tar.gz -C /data .
```

---

## 📊 **Monitoreo**

### **Acceso a Interfaces**
```bash
# Abrir API docs
open http://localhost:8000/docs

# Abrir Prometheus
open http://localhost:9090

# Abrir Grafana
open http://localhost:3000
# Usuario: admin
# Contraseña: gridbot123
```

### **Verificar Métricas Específicas**
```bash
# Estado de conexión a Binance
curl http://localhost:9090/api/v1/query?query=binance_connection_status

# Órdenes totales
curl http://localhost:9090/api/v1/query?query=gridbot_orders_total

# Profit/Loss total
curl http://localhost:9090/api/v1/query?query=gridbot_profit_loss_total

# Errores de API
curl http://localhost:9090/api/v1/query?query=binance_api_errors_total
```

### **Alertas**
```bash
# Ver alertas activas
curl http://localhost:9090/api/v1/alerts

# Ver reglas de alerta
curl http://localhost:9090/api/v1/rules
```

---

## 🤖 **Trading**

### **Obtener Información**
```bash
# Balances
curl http://localhost:8000/api/trade/balances

# Precio de un símbolo
curl http://localhost:8000/api/trade/price/BNBUSDT

# Trades recientes
curl http://localhost:8000/api/trade/trades

# Configuración de grid
curl http://localhost:8000/api/strategies/strategy/grid_config
```

### **Ejecutar Operaciones**
```bash
# Ejecutar grid trading
curl -X POST "http://localhost:8000/api/trade/run_grid" \
  -H "Authorization: Bearer tu_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BNBUSDT",
    "grid_levels": 10,
    "investment_amount": 100,
    "price_range": 0.05
  }'

# Crear orden
curl -X POST "http://localhost:8000/api/trade/order" \
  -H "Authorization: Bearer tu_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BNBUSDT",
    "side": "BUY",
    "order_type": "MARKET",
    "quantity": 0.001
  }'

# Ejecutar backtest
curl -X POST "http://localhost:8000/api/strategies/strategy/backtest" \
  -H "Authorization: Bearer tu_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "strategy": "grid",
    "symbol": "BNBUSDT",
    "start_date": "2024-01-01",
    "end_date": "2024-01-31"
  }'
```

---

## 🛠️ **Solución de Problemas**

### **Error 1022 (Signature Invalid)**
```bash
# Verificar credenciales
docker-compose exec api python3 verify_binance_credentials.py

# Verificar IP
curl ifconfig.me

# Verificar permisos en Binance
# Ve a Binance.com → Profile → API Management
```

### **Error de Conexión a Base de Datos**
```bash
# Verificar estado de PostgreSQL
docker-compose logs db

# Reiniciar base de datos
docker-compose restart db

# Verificar conectividad
docker-compose exec api ping db
```

### **Prometheus no recibe métricas**
```bash
# Verificar configuración
docker-compose exec prometheus cat /etc/prometheus/prometheus.yml

# Verificar targets
curl http://localhost:9090/api/v1/targets

# Reiniciar Prometheus
docker-compose restart prometheus
```

### **Grafana no muestra datos**
```bash
# Verificar datasource
# Ve a Grafana → Configuration → Data sources

# Verificar queries
# Edita un panel y verifica la sintaxis PromQL

# Reiniciar Grafana
docker-compose restart grafana
```

---

## 🔒 **Seguridad**

### **Verificar Configuración de Seguridad**
```bash
# Verificar variables de entorno
docker-compose exec api env | grep -E "(API_KEY|BINANCE)"

# Verificar logs de autenticación
docker-compose logs api | grep -i "auth\|unauthorized"

# Verificar rate limiting
docker-compose logs api | grep -i "rate limit"
```

### **Rotar Credenciales**
```bash
# Generar nueva API Key
openssl rand -hex 32

# Actualizar .env
nano .env

# Reiniciar servicios
docker-compose restart api
```

---

## 📈 **Optimización**

### **Performance**
```bash
# Ver uso de recursos
docker stats

# Ver logs de performance
docker-compose logs api | grep -i "performance\|slow"

# Optimizar base de datos
docker-compose exec db psql -U griduser -d gridbot -c "VACUUM ANALYZE;"
```

### **Limpieza**
```bash
# Limpiar logs antiguos
docker system prune -f

# Limpiar volúmenes no usados
docker volume prune -f

# Limpiar imágenes no usadas
docker image prune -f
```

---

## 📞 **Soporte**

### **Comandos de Diagnóstico**
```bash
# Estado completo del sistema
docker-compose ps && echo "---" && docker stats --no-stream

# Verificar conectividad
docker-compose exec api ping -c 3 api.binance.com

# Verificar puertos
netstat -tulpn | grep -E "(8000|9090|3000|5432)"

# Verificar logs de errores
docker-compose logs | grep -i "error\|exception\|traceback"
```

### **Información del Sistema**
```bash
# Versiones de software
docker --version
docker-compose --version
git --version

# Información del host
uname -a
df -h
free -h
```

---

## 🎯 **Comandos de Desarrollo**

### **Desarrollo Local**
```bash
# Ejecutar en modo desarrollo
docker-compose -f docker-compose.dev.yml up -d

# Ver logs en tiempo real
docker-compose logs -f api

# Ejecutar tests
docker-compose exec api python -m pytest

# Ejecutar linting
docker-compose exec api flake8 app/
```

### **Debugging**
```bash
# Entrar al contenedor
docker-compose exec api bash

# Verificar Python packages
docker-compose exec api pip list

# Verificar variables de entorno
docker-compose exec api env

# Ejecutar script de debug
docker-compose exec api python3 debug_script.py
```

---

**💡 Tip:** Usa `alias` para crear comandos personalizados:

```bash
# Agregar al .bashrc o .zshrc
alias gridbot-status='docker-compose ps'
alias gridbot-logs='docker-compose logs -f api'
alias gridbot-restart='docker-compose restart api'
alias gridbot-balances='curl http://localhost:8000/api/trade/balances'
alias gridbot-price='curl http://localhost:8000/api/trade/price/BNBUSDT'
```

---

**🎉 ¡GridBot está listo para operar!**

Para más información, consulta la documentación completa en los archivos markdown del proyecto.
