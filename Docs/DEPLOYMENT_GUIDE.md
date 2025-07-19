# 🚀 Guía de Despliegue de GridBot

## 📋 **Tabla de Contenidos**

1. [Requisitos del Sistema](#requisitos-del-sistema)
2. [Instalación](#instalación)
3. [Configuración](#configuración)
4. [Configuración de Binance](#configuración-de-binance)
5. [Despliegue](#despliegue)
6. [Verificación](#verificación)
7. [Monitoreo](#monitoreo)
8. [Mantenimiento](#mantenimiento)
9. [Solución de Problemas](#solución-de-problemas)
10. [Seguridad](#seguridad)

---

## 🖥️ **Requisitos del Sistema**

### **Sistema Operativo:**
- ✅ **Linux** (Ubuntu 20.04+ recomendado)
- ✅ **macOS** (10.15+)
- ✅ **Windows** (con WSL2)

### **Software Requerido:**
- ✅ **Docker** (20.10+)
- ✅ **Docker Compose** (2.0+)
- ✅ **Git** (2.25+)

### **Recursos Mínimos:**
- **CPU:** 2 cores
- **RAM:** 4 GB
- **Almacenamiento:** 20 GB
- **Red:** Conexión estable a internet

### **Puertos Requeridos:**
- **8000:** GridBot API
- **5432:** PostgreSQL
- **9090:** Prometheus
- **3000:** Grafana
- **6379:** Redis (opcional)

---

## 📦 **Instalación**

### **1. Clonar el Repositorio**
```bash
git clone https://github.com/tu-usuario/grid_bot.git
cd grid_bot
```

### **2. Verificar Docker**
```bash
# Verificar Docker
docker --version
docker-compose --version

# Verificar que Docker esté ejecutándose
docker info
```

### **3. Configurar Variables de Entorno**
```bash
# Copiar archivo de ejemplo
cp .env.example .env

# Editar variables de entorno
nano .env
```

---

## ⚙️ **Configuración**

### **Archivo .env**
```env
# =============================================================================
# CONFIGURACIÓN DE GRIDBOT
# =============================================================================

# API Key para autenticación interna
API_KEY=tu_api_key_secreta_aqui

# =============================================================================
# BINANCE API
# =============================================================================

# Credenciales de Binance (System Generated)
BINANCE_API_KEY=tu_api_key_de_binance_aqui
BINANCE_API_SECRET=tu_api_secret_de_binance_aqui

# =============================================================================
# BASE DE DATOS
# =============================================================================

# PostgreSQL
POSTGRES_USER=griduser
POSTGRES_PASSWORD=gridpass
POSTGRES_DB=gridbot
POSTGRES_HOST=db
POSTGRES_PORT=5432

# =============================================================================
# TELEGRAM (OPCIONAL)
# =============================================================================

# Bot Token de Telegram
TELEGRAM_BOT_TOKEN=tu_bot_token_aqui
TELEGRAM_CHAT_ID=tu_chat_id_aqui

# =============================================================================
# REDIS (OPCIONAL)
# =============================================================================

# Redis para cache
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0

# =============================================================================
# MONITOREO
# =============================================================================

# Prometheus
PROMETHEUS_PORT=9090

# Grafana
GRAFANA_PORT=3000
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=gridbot123
```

---

## 🔐 **Configuración de Binance**

### **1. Crear API Key en Binance**

#### **Acceder a Binance:**
1. Ve a **Binance.com**
2. Inicia sesión con tu cuenta
3. Ve a **Profile** → **API Management**

#### **Crear Nueva API Key:**
1. Haz clic en **Create API**
2. Selecciona **System generated**
3. Completa la verificación de seguridad

#### **Configurar Permisos:**
```
✅ IP Restrictions: [TU_IP_AQUI]
✅ Enable Reading
✅ Enable Spot & Margin Trading
❌ Enable Margin Loan, Repay & Transfer
❌ Enable Futures
❌ Permits Universal Transfer
❌ Enable Withdrawals
❌ Enable Symbol Whitelist
```

#### **Configurar Restricciones de IP:**
1. Ve a **Restrict Access**
2. Agrega tu IP pública
3. Obtén tu IP: `curl ifconfig.me`

### **2. Verificar Credenciales**
```bash
# Ejecutar verificación
docker-compose exec api python3 verify_binance_credentials.py
```

---

## 🚀 **Despliegue**

### **1. Despliegue Inicial**
```bash
# Construir y levantar servicios
docker-compose up -d

# Verificar estado
docker-compose ps
```

### **2. Verificar Logs**
```bash
# Ver logs de todos los servicios
docker-compose logs

# Ver logs específicos
docker-compose logs api
docker-compose logs db
docker-compose logs prometheus
docker-compose logs grafana
```

### **3. Verificar Servicios**
```bash
# Verificar API
curl http://localhost:8000/docs

# Verificar Prometheus
curl http://localhost:9090/-/healthy

# Verificar Grafana
curl http://localhost:3000/api/health
```

---

## ✅ **Verificación**

### **1. Verificar Conexión a Binance**
```bash
# Ejecutar script de verificación
docker-compose exec api python3 verify_binance_credentials.py
```

**Resultado esperado:**
```
✅ Credenciales válidas
Tipo de cuenta: SPOT
Balances con saldo: X
```

### **2. Verificar Endpoints de GridBot**
```bash
# Verificar balances
curl http://localhost:8000/api/trade/balances

# Verificar precios
curl http://localhost:8000/api/trade/price/BNBUSDT

# Verificar métricas
curl http://localhost:8000/api/metrics/metrics/
```

### **3. Verificar Monitoreo**
```bash
# Acceder a Prometheus
open http://localhost:9090

# Acceder a Grafana
open http://localhost:3000
# Usuario: admin
# Contraseña: gridbot123
```

---

## 📊 **Monitoreo**

### **1. Prometheus**
- **URL:** http://localhost:9090
- **Métricas principales:**
  - `gridbot_orders_total`
  - `gridbot_volume_total`
  - `gridbot_profit_loss`
  - `binance_connection_status`

### **2. Grafana**
- **URL:** http://localhost:3000
- **Credenciales:**
  - Usuario: `admin`
  - Contraseña: `gridbot123`
- **Dashboard:** GridBot Overview

### **3. Alertas de Telegram**
- Configurar bot de Telegram
- Recibir notificaciones de:
  - Órdenes ejecutadas
  - Errores de API
  - Cambios de balance

---

## 🔧 **Mantenimiento**

### **1. Actualizaciones**
```bash
# Actualizar código
git pull origin main

# Reconstruir contenedores
docker-compose down
docker-compose up -d --build
```

### **2. Backups**
```bash
# Backup de base de datos
docker-compose exec db pg_dump -U griduser gridbot > backup_$(date +%Y%m%d).sql

# Backup de configuración
cp .env backup_env_$(date +%Y%m%d)
```

### **3. Logs**
```bash
# Ver logs recientes
docker-compose logs --tail=100 api

# Limpiar logs antiguos
docker system prune -f
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
```

### **Error de Conexión a Base de Datos**
```bash
# Verificar estado de PostgreSQL
docker-compose logs db

# Reiniciar base de datos
docker-compose restart db
```

### **Error de API**
```bash
# Verificar logs de API
docker-compose logs api

# Reiniciar API
docker-compose restart api
```

### **Problemas de Métricas**
```bash
# Verificar Prometheus
curl http://localhost:9090/-/healthy

# Verificar configuración
docker-compose exec prometheus cat /etc/prometheus/prometheus.yml
```

---

## 🔒 **Seguridad**

### **1. API Keys**
- ✅ Usar API Keys con restricciones de IP
- ✅ No compartir credenciales
- ✅ Rotar API Keys regularmente
- ✅ Usar permisos mínimos

### **2. Red**
- ✅ Restringir acceso a puertos
- ✅ Usar firewall
- ✅ Monitorear conexiones
- ✅ Usar HTTPS en producción

### **3. Base de Datos**
- ✅ Cambiar contraseñas por defecto
- ✅ Usar conexiones seguras
- ✅ Hacer backups regulares
- ✅ Monitorear accesos

### **4. Contenedores**
- ✅ Mantener imágenes actualizadas
- ✅ Escanear vulnerabilidades
- ✅ Usar recursos limitados
- ✅ Monitorear logs

---

## 📞 **Soporte**

### **Logs Útiles**
```bash
# Logs de aplicación
docker-compose logs api

# Logs de base de datos
docker-compose logs db

# Logs de monitoreo
docker-compose logs prometheus
docker-compose logs grafana
```

### **Comandos de Diagnóstico**
```bash
# Estado de servicios
docker-compose ps

# Uso de recursos
docker stats

# Verificar conectividad
docker-compose exec api ping binance.com
```

### **Contacto**
- **Issues:** GitHub Issues
- **Documentación:** README.md
- **Wiki:** Documentación adicional

---

## 🎯 **Próximos Pasos**

### **1. Configurar Estrategias**
- Configurar grid trading
- Ajustar parámetros
- Probar en modo simulación

### **2. Configurar Alertas**
- Configurar Telegram
- Configurar email
- Configurar webhooks

### **3. Optimización**
- Ajustar recursos
- Optimizar consultas
- Configurar cache

---

**🎉 ¡GridBot está listo para operar!**

Para más información, consulta la documentación adicional en la carpeta `Docs/`. 