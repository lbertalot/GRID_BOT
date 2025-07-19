# 🤖 GridBot - Bot de Trading Automatizado

[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)](https://www.docker.com/)
[![Python](https://img.shields.io/badge/Python-3.11+-green.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-red.svg)](https://fastapi.tiangolo.com/)
[![Prometheus](https://img.shields.io/badge/Prometheus-Monitoring-orange.svg)](https://prometheus.io/)
[![Grafana](https://img.shields.io/badge/Grafana-Dashboards-purple.svg)](https://grafana.com/)

> **GridBot** es un bot de trading automatizado avanzado que utiliza estrategias de grid trading para operar en Binance. Incluye monitoreo completo con Prometheus y Grafana, alertas en tiempo real, y una API REST robusta.

## 🚀 **Características Principales**

### **🤖 Trading Automatizado**
- ✅ **Grid Trading** - Estrategia de trading automatizado
- ✅ **Múltiples Estrategias** - RSI, MACD, Scalping, Trailing Stop
- ✅ **Gestión de Riesgo** - Stop-loss y take-profit automáticos
- ✅ **Backtesting** - Prueba estrategias con datos históricos
- ✅ **Modo Simulación** - Prueba sin riesgo real

### **📊 Monitoreo Avanzado**
- ✅ **Prometheus** - Métricas en tiempo real
- ✅ **Grafana** - Dashboards interactivos
- ✅ **Alertas** - Notificaciones automáticas
- ✅ **Telegram** - Alertas en tiempo real
- ✅ **Métricas Personalizadas** - KPIs específicos de trading

### **🔐 Seguridad y Confiabilidad**
- ✅ **API Key Segura** - Restricciones de IP
- ✅ **Permisos Mínimos** - Solo lo necesario
- ✅ **Sin Retiros** - Protección de fondos
- ✅ **Logs Detallados** - Auditoría completa
- ✅ **Backups Automáticos** - Datos protegidos

### **⚡ API REST Robusta**
- ✅ **FastAPI** - API moderna y rápida
- ✅ **Documentación Automática** - Swagger UI
- ✅ **Autenticación** - API Key protegida
- ✅ **Rate Limiting** - Protección contra abuso
- ✅ **Validación** - Pydantic models

## 📋 **Tabla de Contenidos**

1. [Instalación Rápida](#instalación-rápida)
2. [Configuración](#configuración)
3. [Uso](#uso)
4. [Monitoreo](#monitoreo)
5. [API](#api)
6. [Estrategias](#estrategias)
7. [Documentación](#documentación)
8. [Soporte](#soporte)

---

## ⚡ **Instalación Rápida**

### **Prerrequisitos**
```bash
# Verificar Docker
docker --version
docker-compose --version

# Verificar Git
git --version
```

### **Instalación en 3 Pasos**

#### **1. Clonar Repositorio**
```bash
git clone https://github.com/tu-usuario/grid_bot.git
cd grid_bot
```

#### **2. Configurar Variables**
```bash
# Copiar archivo de ejemplo
cp .env.example .env

# Editar configuración
nano .env
```

#### **3. Desplegar**
```bash
# Levantar servicios
docker-compose up -d

# Verificar estado
docker-compose ps
```

### **Verificación Rápida**
```bash
# Verificar API
curl http://localhost:8000/docs

# Verificar Prometheus
curl http://localhost:9090/-/healthy

# Verificar Grafana
curl http://localhost:3000/api/health
```

---

## ⚙️ **Configuración**

### **Configuración de Binance**

#### **1. Crear API Key**
1. Ve a **Binance.com** → **Profile** → **API Management**
2. Haz clic en **Create API**
3. Selecciona **System generated**
4. Configura permisos:
   ```
   ✅ IP Restrictions: [TU_IP]
   ✅ Enable Reading
   ✅ Enable Spot & Margin Trading
   ❌ Enable Withdrawals
   ```

#### **2. Obtener IP del Servidor**
```bash
curl ifconfig.me
```

#### **3. Actualizar Configuración**
```env
# En archivo .env
BINANCE_API_KEY=tu_api_key_aqui
BINANCE_API_SECRET=tu_api_secret_aqui
```

#### **4. Verificar Conexión**
```bash
docker-compose exec api python3 verify_binance_credentials.py
```

### **Configuración de Telegram (Opcional)**
```env
# En archivo .env
TELEGRAM_BOT_TOKEN=tu_bot_token_aqui
TELEGRAM_CHAT_ID=tu_chat_id_aqui
```

---

## 🎯 **Uso**

### **Acceso a Interfaces**

#### **API Documentation**
- **URL:** http://localhost:8000/docs
- **Descripción:** Documentación interactiva de la API

#### **Prometheus**
- **URL:** http://localhost:9090
- **Descripción:** Métricas y alertas

#### **Grafana**
- **URL:** http://localhost:3000
- **Usuario:** `admin`
- **Contraseña:** `gridbot123`
- **Descripción:** Dashboards y visualizaciones

### **Comandos Básicos**

#### **Verificar Estado**
```bash
# Estado de servicios
docker-compose ps

# Logs de API
docker-compose logs api

# Logs de todos los servicios
docker-compose logs
```

#### **Obtener Balances**
```bash
curl http://localhost:8000/api/trade/balances
```

#### **Obtener Precios**
```bash
curl http://localhost:8000/api/trade/price/BNBUSDT
```

#### **Ejecutar Grid Trading**
```bash
curl -X POST "http://localhost:8000/api/trade/run_grid" \
  -H "Authorization: Bearer tu_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BNBUSDT",
    "grid_levels": 10,
    "investment_amount": 100,
    "price_range": 0.05
  }'
```

---

## 📊 **Monitoreo**

### **Dashboards Disponibles**

#### **GridBot Overview**
- Estado de conexión a Binance
- Órdenes por minuto
- Profit/Loss total
- Volumen total
- Errores de API

#### **Trading Performance**
- Tasa de éxito de órdenes
- Profit/Loss por estrategia
- Volumen por símbolo
- Distribución de órdenes

#### **System Health**
- Uso de CPU y memoria
- Conexiones a base de datos
- Tiempo de respuesta de API
- Estado de servicios

### **Alertas Configuradas**
- 🔴 **Conexión perdida** a Binance
- 🟡 **Errores de API** frecuentes
- 🔴 **Pérdidas significativas**
- 🟡 **Alto uso de recursos**

---

## 🔌 **API**

### **Endpoints Principales**

#### **Trading**
```
GET  /api/trade/balances          # Obtener balances
GET  /api/trade/price/{symbol}     # Obtener precio
POST /api/trade/order              # Crear orden
POST /api/trade/run_grid           # Ejecutar grid trading
GET  /api/trade/trades             # Obtener trades
```

#### **Estrategias**
```
GET  /api/strategies/strategy/grid_config    # Configuración de grid
POST /api/strategies/strategy/backtest       # Ejecutar backtest
GET  /api/strategies/strategy/rsi_macd       # Estrategia RSI+MACD
GET  /api/strategies/strategy/scalping       # Estrategia Scalping
GET  /api/strategies/strategy/trailing_stop  # Estrategia Trailing Stop
```

#### **Métricas**
```
GET  /api/metrics/metrics/         # Métricas de Prometheus
GET  /api/metrics/metrics/trading  # Métricas de trading
GET  /api/metrics/metrics/binance  # Métricas de Binance
GET  /api/metrics/metrics/strategies # Métricas de estrategias
```

### **Autenticación**
```bash
# Incluir API Key en headers
curl -H "Authorization: Bearer tu_api_key" \
  http://localhost:8000/api/trade/balances
```

---

## 📈 **Estrategias**

### **Grid Trading**
- **Descripción:** Estrategia de trading automatizado basada en niveles de precio
- **Configuración:** Niveles de grid, rango de precio, cantidad de inversión
- **Ventajas:** Automatización completa, gestión de riesgo integrada

### **RSI + MACD**
- **Descripción:** Combinación de indicadores técnicos RSI y MACD
- **Configuración:** Períodos RSI, señales MACD, thresholds
- **Ventajas:** Señales de entrada/salida precisas

### **Scalping**
- **Descripción:** Trading de alta frecuencia con pequeñas ganancias
- **Configuración:** Tiempo de hold, tamaño de posición, stop-loss
- **Ventajas:** Ganancias rápidas, bajo riesgo por operación

### **Trailing Stop**
- **Descripción:** Stop-loss dinámico que sigue el precio
- **Configuración:** Porcentaje de trailing, activación
- **Ventajas:** Protección de ganancias, maximización de beneficios

---

## 📚 **Documentación**

### **Guías Principales**
- 📖 **[Guía de Despliegue](Docs/DEPLOYMENT_GUIDE.md)** - Instalación y configuración completa
- 🔐 **[Configuración de Binance](Docs/BINANCE_SETUP_GUIDE.md)** - Setup de API Key y permisos
- 📊 **[Guía de Monitoreo](Docs/MONITORING_GUIDE.md)** - Prometheus y Grafana
- 🛠️ **[Solución de Problemas](Docs/SOLUCION_ERROR_1022.md)** - Errores comunes y soluciones

### **Documentación Técnica**
- 📋 **[PRD](Docs/PRD.md)** - Product Requirements Document
- 📚 **[Índice de Documentación](Docs/README.md)** - Todas las guías organizadas
- 🔧 **[API Reference](http://localhost:8000/docs)** - Documentación de API
- 📊 **[Métricas](http://localhost:9090)** - Métricas de Prometheus
- 📈 **[Dashboards](http://localhost:3000)** - Dashboards de Grafana

---

## 🛠️ **Soporte**

### **Comandos de Diagnóstico**
```bash
# Verificar credenciales de Binance
docker-compose exec api python3 verify_binance_credentials.py

# Verificar estado de API Key
docker-compose exec api python3 check_api_key_status.py

# Ver logs de errores
docker-compose logs api | grep -i "error"

# Verificar métricas
curl http://localhost:8000/api/metrics/metrics/
```

### **Problemas Comunes**

#### **Error 1022: Signature Invalid**
```bash
# Verificar credenciales
docker-compose exec api python3 verify_binance_credentials.py

# Verificar IP
curl ifconfig.me

# Verificar permisos en Binance
```

#### **Error de Conexión a Base de Datos**
```bash
# Verificar estado de PostgreSQL
docker-compose logs db

# Reiniciar base de datos
docker-compose restart db
```

#### **Prometheus no recibe métricas**
```bash
# Verificar configuración
docker-compose exec prometheus cat /etc/prometheus/prometheus.yml

# Reiniciar Prometheus
docker-compose restart prometheus
```

### **Recursos Adicionales**
- 📖 **[Documentación Binance](https://binance-docs.github.io/apidocs/)**
- 📊 **[Prometheus Docs](https://prometheus.io/docs/)**
- 📈 **[Grafana Docs](https://grafana.com/docs/)**
- 🐍 **[FastAPI Docs](https://fastapi.tiangolo.com/)**

---

## 🤝 **Contribuir**

### **Reportar Issues**
1. Ve a **[Issues](https://github.com/tu-usuario/grid_bot/issues)**
2. Busca si el problema ya existe
3. Crea un nuevo issue con:
   - Descripción del problema
   - Pasos para reproducir
   - Logs relevantes
   - Configuración del sistema

### **Pull Requests**
1. Fork el repositorio
2. Crea una rama para tu feature
3. Haz commit de tus cambios
4. Push a la rama
5. Crea un Pull Request

### **Código de Conducta**
- Respeto mutuo
- Comunicación constructiva
- Colaboración abierta
- Aprendizaje continuo

---

## 📄 **Licencia**

Este proyecto está bajo la Licencia MIT. Ver el archivo [LICENSE](LICENSE) para más detalles.

---

## 🙏 **Agradecimientos**

- **Binance** por su API robusta y documentación
- **FastAPI** por el framework web moderno
- **Prometheus** por el sistema de monitoreo
- **Grafana** por las visualizaciones
- **Docker** por la containerización

---

## 📞 **Contacto**

- **Issues:** [GitHub Issues](https://github.com/tu-usuario/grid_bot/issues)
- **Documentación:** [Wiki](https://github.com/tu-usuario/grid_bot/wiki)
- **Discussions:** [GitHub Discussions](https://github.com/tu-usuario/grid_bot/discussions)

---

**🎉 ¡GridBot está listo para operar!**

Para comenzar, sigue la [Guía de Despliegue](Docs/DEPLOYMENT_GUIDE.md) y configura tu [API Key de Binance](Docs/BINANCE_SETUP_GUIDE.md).

---

<div align="center">

**⭐ Si te gusta GridBot, ¡dale una estrella al repositorio!**

[![GitHub stars](https://img.shields.io/github/stars/tu-usuario/grid_bot?style=social)](https://github.com/tu-usuario/grid_bot)
[![GitHub forks](https://img.shields.io/github/forks/tu-usuario/grid_bot?style=social)](https://github.com/tu-usuario/grid_bot)

</div> 