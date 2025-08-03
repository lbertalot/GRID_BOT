# 🚀 GridBot Trading Platform - Guía de Ejecución Completa

## 📋 Resumen del Proyecto

**GridBot** es una plataforma completa de trading automatizado que incluye:

- 🤖 **Trading automático** con estrategia Grid
- 📊 **Monitoreo en tiempo real** con Grafana y Prometheus
- 📱 **Notificaciones por Telegram**
- 🔄 **Tareas asíncronas** con Celery
- 🛡️ **Gestión de riesgos** automática
- 📈 **Métricas y análisis** avanzados

---

## ✅ Estado Actual del Sistema

**¡Todos los servicios funcionando correctamente!**

| Servicio | Estado | Puerto | URL |
|----------|--------|--------|-----|
| **API FastAPI** | ✅ Funcionando | 8000 | http://localhost:8000 |
| **Grafana** | ✅ Funcionando | 3000 | http://localhost:3000 |
| **Prometheus** | ✅ Funcionando | 9090 | http://localhost:9090 |
| **Flower** | ✅ Funcionando | 5555 | http://localhost:5555 |
| **PostgreSQL** | ✅ Funcionando | 5432 | localhost:5432 |
| **Redis** | ✅ Funcionando | 6379 | localhost:6379 |
| **Nginx** | ✅ Funcionando | 80/443 | http://localhost |
| **Alertmanager** | ✅ Funcionando | 9093 | http://localhost:9093 |
| **Celery Worker** | ✅ Funcionando | - | - |
| **Celery Beat** | ✅ Funcionando | - | - |

---

## 🚀 Inicio Rápido

### 1. Verificar que el sistema esté funcionando

```bash
# Ver estado de todos los servicios
docker-compose ps

# Verificar API
curl http://localhost:8000/health

# Verificar interfaces web
open http://localhost:8000      # Dashboard principal
open http://localhost:3000      # Grafana
open http://localhost:5555      # Flower (monitoreo Celery)
```

### 2. Configurar credenciales (OBLIGATORIO)

```bash
# Copiar archivo de configuración
cp config_example.env .env

# Editar con tus credenciales
nano .env
```

**Variables obligatorias a configurar:**
```bash
# Binance API Keys
BINANCE_API_KEY=tu_api_key_de_binance
BINANCE_SECRET_KEY=tu_secret_key_de_binance

# Telegram Bot
TELEGRAM_BOT_TOKEN=tu_token_de_telegram
TELEGRAM_CHAT_ID=tu_chat_id_de_telegram
```

### 3. Ejecutar configuración automática

```bash
# Ejecutar script de configuración
./scripts/setup_trading.sh
```

Este script:
- ✅ Valida tu configuración
- ✅ Prueba conexión con Binance
- ✅ Prueba notificaciones de Telegram
- ✅ Obtiene tu balance
- ✅ Te pregunta si iniciar trading

---

## 📚 Guía Completa para Principiantes

### ¿Eres nuevo en criptomonedas?

**¡No te preocupes!** Hemos creado una guía completa:

📖 **[GUIA_USUARIO_PRINCIPIANTE.md](GUIA_USUARIO_PRINCIPIANTE.md)**

Esta guía incluye:
- 🤔 ¿Qué es GridBot y cómo funciona?
- 🏦 Cómo crear cuenta en Binance paso a paso
- 🔑 Cómo configurar API Keys de forma segura
- 📱 Cómo configurar Telegram para notificaciones
- ⚙️ Configuración completa del sistema
- 📊 Cómo monitorear el trading
- 🔧 Solución de problemas comunes
- 📚 Glosario de términos

---

## 🎯 Configuración Paso a Paso

### Paso 1: Crear cuenta en Binance

1. **Ir a**: https://www.binance.com
2. **Registrarse** con tu email
3. **Verificar identidad** (KYC)
4. **Depositar fondos** (empieza con $50-100)
5. **Crear API Keys**:
   - Perfil → API Management → Create API
   - ✅ Enable Spot & Margin Trading
   - ❌ NO marcar "Enable Withdrawals" (seguridad)

### Paso 2: Configurar Telegram

1. **Descargar Telegram**: https://telegram.org
2. **Buscar @BotFather** en Telegram
3. **Enviar**: `/newbot`
4. **Seguir instrucciones** para crear tu bot
5. **Guardar el token** que te da BotFather
6. **Obtener Chat ID**:
   - Enviar mensaje a tu bot
   - Ir a: `https://api.telegram.org/bot<TU_TOKEN>/getUpdates`
   - Buscar `"chat":{"id":123456789}`

### Paso 3: Configurar archivo .env

```bash
# Copiar archivo de ejemplo
cp config_example.env .env

# Editar con tus credenciales
nano .env
```

**Configuración mínima:**
```bash
BINANCE_API_KEY=abc123def456ghi789jkl012mno345pqr678stu901vwx234yz
BINANCE_SECRET_KEY=secret123secret456secret789secret012secret345
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=123456789
```

### Paso 4: Ejecutar sistema

```bash
# Opción 1: Configuración automática
./scripts/setup_trading.sh

# Opción 2: Manual
docker-compose up -d
curl -X POST "http://localhost:8000/api/v1/trading/start"
```

---

## 📊 Monitoreo del Sistema

### Interfaces Web Disponibles

| Interfaz | URL | Usuario/Contraseña | Descripción |
|----------|-----|-------------------|-------------|
| **Dashboard** | http://localhost:8000 | - | Panel principal |
| **Grafana** | http://localhost:3000 | admin/gridbot123 | Métricas y gráficos |
| **Prometheus** | http://localhost:9090 | - | Datos de monitoreo |
| **Flower** | http://localhost:5555 | - | Monitoreo de tareas |

### Notificaciones por Telegram

Recibirás mensajes como:
```
🤖 GridBot - Nueva orden ejecutada
📈 Compra: 0.001 BTC a $45,000
💰 Ganancia: +$5.50
📊 Balance total: $1,250.75
```

### Comandos Útiles

```bash
# Ver estado del sistema
docker-compose ps

# Ver logs en tiempo real
docker-compose logs -f api

# Ver métricas de trading
curl http://localhost:8000/api/v1/metrics

# Detener trading
curl -X POST http://localhost:8000/api/v1/trading/stop

# Ver configuración
curl http://localhost:8000/api/v1/config

# Probar Telegram
curl -X POST http://localhost:8000/api/v1/test/telegram

# Probar Binance
curl http://localhost:8000/api/v1/test/binance
```

---

## 🔧 Solución de Problemas

### ❌ Problema: "No se puede conectar a Binance"

**Solución:**
```bash
# Verificar API Keys
grep "BINANCE_API_KEY" .env

# Probar conexión
curl http://localhost:8000/api/v1/test/binance

# Ver logs
docker-compose logs api | grep -i binance
```

### ❌ Problema: "No recibo mensajes de Telegram"

**Solución:**
```bash
# Verificar configuración
grep "TELEGRAM" .env

# Probar Telegram
curl -X POST http://localhost:8000/api/v1/test/telegram

# Verificar que hiciste "Start" al bot
```

### ❌ Problema: "Los servicios no inician"

**Solución:**
```bash
# Parar todo
docker-compose down

# Limpiar volúmenes
docker-compose down -v

# Reconstruir
docker-compose build --no-cache

# Iniciar
docker-compose up -d
```

### ❌ Problema: "No hay fondos suficientes"

**Solución:**
1. Depositar más dinero en Binance
2. Verificar balance: `curl http://localhost:8000/api/v1/balance`
3. Ajustar cantidad por operación en `.env`

---

## 📈 Configuración Avanzada

### Parámetros de Trading

```bash
# En el archivo .env
TRADING_PAIR=BTCUSDT          # Par de trading
GRID_LEVELS=10                # Niveles de grid
MIN_PRICE=45000               # Precio mínimo
MAX_PRICE=55000               # Precio máximo
QUANTITY_PER_TRADE=0.001      # Cantidad por operación
```

### Gestión de Riesgos

```bash
MAX_DAILY_LOSS=5.0            # Pérdida máxima diaria (%)
STOP_LOSS=10.0                # Stop loss (%)
MAX_POSITION_SIZE=20.0        # Tamaño máximo de posición (%)
```

### Notificaciones

```bash
PROFIT_ALERT_THRESHOLD=5.0    # Alerta de ganancia (%)
LOSS_ALERT_THRESHOLD=3.0      # Alerta de pérdida (%)
```

---

## 🎯 Comandos de Inicio Rápido

### Para usuarios principiantes:

```bash
# 1. Verificar sistema
docker-compose ps

# 2. Configurar credenciales
cp config_example.env .env
nano .env

# 3. Ejecutar configuración automática
./scripts/setup_trading.sh
```

### Para usuarios avanzados:

```bash
# 1. Iniciar servicios
docker-compose up -d

# 2. Verificar estado
curl http://localhost:8000/health

# 3. Iniciar trading
curl -X POST "http://localhost:8000/api/v1/trading/start"

# 4. Monitorear
docker-compose logs -f api
```

---

## 📚 Documentación Adicional

- 📖 **[GUIA_USUARIO_PRINCIPIANTE.md](GUIA_USUARIO_PRINCIPIANTE.md)** - Guía completa para principiantes
- 📊 **[REPORTE_ESTADO_FINAL.md](REPORTE_ESTADO_FINAL.md)** - Estado técnico del sistema
- ⚙️ **[config_example.env](config_example.env)** - Archivo de configuración de ejemplo
- 🔧 **[scripts/setup_trading.sh](scripts/setup_trading.sh)** - Script de configuración automática

---

## 🎉 ¡Listo para Trading!

Una vez configurado, GridBot:

- ✅ **Funciona 24/7** automáticamente
- ✅ **Te envía notificaciones** por Telegram
- ✅ **Muestra métricas** en tiempo real
- ✅ **Gestiona riesgos** automáticamente
- ✅ **Se adapta** a cambios de mercado

### ⚠️ Recordatorios importantes:

1. **Empieza con poco dinero** ($50-100)
2. **Monitorea regularmente** el sistema
3. **Lee las notificaciones** de Telegram
4. **No compartas tus claves** con nadie
5. **El trading tiene riesgos** - puedes ganar o perder

---

## 🆘 Soporte

- 📧 **Email**: soporte@gridbot.com
- 📱 **Telegram**: @GridBotSupport
- 📖 **Documentación**: https://docs.gridbot.com

---

**¡Que tengas éxito con tu GridBot! 🚀**

---

**Última actualización**: 27 de Julio, 2025  
**Versión**: 2.0.0  
**Estado**: ✅ **OPERATIVO** 