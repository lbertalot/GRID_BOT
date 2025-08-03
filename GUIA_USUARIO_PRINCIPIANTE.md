# 🚀 Guía Completa para Usuarios Principiantes - GridBot Trading Platform

## 📋 Tabla de Contenidos
1. [¿Qué es GridBot?](#qué-es-gridbot)
2. [¿Qué necesitas saber antes de empezar?](#qué-necesitas-saber-antes-de-empezar)
3. [Configuración paso a paso](#configuración-paso-a-paso)
4. [Crear cuenta en Binance](#crear-cuenta-en-binance)
5. [Configurar API Keys](#configurar-api-keys)
6. [Configurar Telegram](#configurar-telegram)
7. [Ejecutar el sistema](#ejecutar-el-sistema)
8. [Monitorear el trading](#monitorear-el-trading)
9. [Solución de problemas](#solución-de-problemas)
10. [Glosario de términos](#glosario-de-términos)

---

## 🤖 ¿Qué es GridBot?

**GridBot** es un sistema automatizado de trading que compra y vende criptomonedas automáticamente para generar ganancias. Funciona como un "robot trader" que:

- ✅ **Compra cuando el precio baja**
- ✅ **Vende cuando el precio sube**
- ✅ **Funciona 24/7 sin parar**
- ✅ **Te envía notificaciones por Telegram**
- ✅ **Te muestra estadísticas en tiempo real**

### 🎯 ¿Cómo funciona?

Imagina que tienes una tienda que vende manzanas:
- Si las manzanas bajan de precio → **Compras más**
- Si las manzanas suben de precio → **Vendes las que tienes**
- Repites esto muchas veces → **Ganas dinero**

GridBot hace exactamente lo mismo, pero con criptomonedas como Bitcoin (BTC) y Ethereum (ETH).

---

## 📚 ¿Qué necesitas saber antes de empezar?

### ⚠️ **Advertencias importantes:**
- **El trading tiene riesgos** - Puedes ganar o perder dinero
- **Empieza con poco dinero** - No inviertas más de lo que puedas permitirte perder
- **El sistema es automático** - Una vez configurado, funciona solo
- **Monitorea regularmente** - Revisa el estado del sistema

### 💰 **Conceptos básicos:**
- **Criptomoneda**: Dinero digital (como Bitcoin, Ethereum)
- **Exchange**: Plataforma donde compras/vendes criptomonedas (Binance)
- **API Key**: Clave secreta para conectar GridBot con Binance
- **Grid Trading**: Estrategia de compra/venta automática

---

## ⚙️ Configuración paso a paso

### Paso 1: Verificar que tienes Docker instalado

```bash
# Abre la terminal y ejecuta:
docker --version
docker-compose --version
```

Si no tienes Docker, descárgalo de: https://www.docker.com/products/docker-desktop

### Paso 2: Descargar el proyecto

```bash
# Si ya tienes el proyecto, ve al directorio:
cd /Users/leandrobertalot/Documents/grid_bot

# Verifica que estás en el directorio correcto:
ls -la
```

Deberías ver archivos como `docker-compose.yml`, `requirements.txt`, etc.

### Paso 3: Verificar que el sistema funciona

```bash
# Iniciar todos los servicios:
./scripts/start.sh

# O manualmente:
docker-compose up -d
```

### Paso 4: Verificar que todo funciona

```bash
# Ver estado de servicios:
docker-compose ps

# Verificar API:
curl http://localhost:8000/health
```

---

## 🏦 Crear cuenta en Binance

### ¿Qué es Binance?
Binance es la plataforma más grande del mundo para comprar y vender criptomonedas. Es como un "banco digital" para criptomonedas.

### Paso a paso:

1. **Ir a Binance**: https://www.binance.com
2. **Hacer clic en "Registrarse"**
3. **Completar el formulario**:
   - Email
   - Contraseña
   - Confirmar contraseña
4. **Verificar email** - Revisa tu bandeja de entrada
5. **Completar verificación KYC** (identidad):
   - Subir foto de tu documento (DNI, pasaporte)
   - Tomar selfie
   - Esperar aprobación (24-48 horas)

### 💳 Depositar dinero:

1. **Ir a "Cartera" → "Depositar"**
2. **Seleccionar tu moneda** (USD, EUR, etc.)
3. **Elegir método de pago**:
   - Tarjeta de crédito/débito
   - Transferencia bancaria
   - Pago móvil
4. **Seguir instrucciones** para completar el depósito

### ⚠️ **Importante:**
- **Empieza con poco dinero** (ej: $50-100)
- **Guarda tu contraseña** en un lugar seguro
- **Habilita autenticación de dos factores** (2FA)

---

## 🔑 Configurar API Keys

### ¿Qué son las API Keys?
Son como "llaves digitales" que permiten a GridBot conectarse a tu cuenta de Binance y hacer operaciones automáticamente.

### Paso a paso:

1. **Iniciar sesión en Binance**
2. **Ir a "Perfil" → "API Management"**
3. **Hacer clic en "Create API"**
4. **Configurar permisos**:
   - ✅ **Enable Spot & Margin Trading**
   - ✅ **Enable Futures**
   - ❌ **Enable Withdrawals** (NO marcar por seguridad)
   - ❌ **Enable Reading** (NO marcar por seguridad)
5. **Hacer clic en "Submit"**
6. **Guardar las claves**:
   - **API Key**: Una cadena larga de letras y números
   - **Secret Key**: Otra cadena larga (más importante)

### ⚠️ **Seguridad:**
- **Nunca compartas tus claves** con nadie
- **Guárdalas en un lugar seguro**
- **Si las pierdes, puedes crear nuevas**

---

## 📱 Configurar Telegram

### ¿Qué es Telegram?
Telegram es una aplicación de mensajería que GridBot usa para enviarte notificaciones sobre tus operaciones.

### Paso a paso:

1. **Descargar Telegram**: https://telegram.org
2. **Crear cuenta** con tu número de teléfono
3. **Buscar el bot**: @BotFather
4. **Enviar mensaje**: `/newbot`
5. **Seguir instrucciones**:
   - Dar nombre al bot (ej: "Mi GridBot")
   - Dar username al bot (ej: "mi_gridbot_bot")
6. **Guardar el token** que te da BotFather
7. **Buscar tu bot** por username
8. **Hacer clic en "Start"**
9. **Obtener tu Chat ID**:
   - Enviar mensaje a tu bot
   - Ir a: https://api.telegram.org/bot<TU_TOKEN>/getUpdates
   - Buscar "chat":{"id":123456789} (ese número es tu Chat ID)

---

## ⚙️ Configurar el archivo .env

### Paso a paso:

1. **Copiar el archivo de ejemplo**:
   ```bash
   cp env.example .env
   ```

2. **Editar el archivo .env**:
   ```bash
   nano .env
   # O usar cualquier editor de texto
   ```

3. **Configurar las variables principales**:
   ```bash
   # Binance API Keys (obligatorio)
   BINANCE_API_KEY=tu_api_key_de_binance
   BINANCE_SECRET_KEY=tu_secret_key_de_binance
   
   # Telegram (obligatorio)
   TELEGRAM_BOT_TOKEN=tu_token_de_telegram
   TELEGRAM_CHAT_ID=tu_chat_id_de_telegram
   
   # Configuración de trading (opcional)
   GRID_LEVELS=10
   MIN_PRICE=45000
   MAX_PRICE=55000
   QUANTITY_PER_TRADE=0.001
   ```

4. **Guardar el archivo**

### 📝 **Ejemplo de configuración**:
```bash
# Binance
BINANCE_API_KEY=abc123def456ghi789jkl012mno345pqr678stu901vwx234yz
BINANCE_SECRET_KEY=secret123secret456secret789secret012secret345

# Telegram
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=123456789

# Trading
GRID_LEVELS=10
MIN_PRICE=45000
MAX_PRICE=55000
QUANTITY_PER_TRADE=0.001
AUTO_REBALANCE=true
```

---

## 🚀 Ejecutar el sistema

### Paso 1: Verificar configuración

```bash
# Verificar que el archivo .env existe:
ls -la .env

# Verificar que las variables están configuradas:
grep "BINANCE_API_KEY" .env
grep "TELEGRAM_BOT_TOKEN" .env
```

### Paso 2: Reiniciar servicios

```bash
# Parar servicios:
docker-compose down

# Iniciar servicios:
docker-compose up -d
```

### Paso 3: Verificar que todo funciona

```bash
# Ver estado de servicios:
docker-compose ps

# Verificar API:
curl http://localhost:8000/health

# Verificar Telegram (deberías recibir un mensaje):
curl -X POST "http://localhost:8000/api/v1/test/telegram"
```

### Paso 4: Iniciar trading

```bash
# Iniciar trading automático:
curl -X POST "http://localhost:8000/api/v1/trading/start"

# Verificar estado:
curl "http://localhost:8000/api/v1/status"
```

---

## 📊 Monitorear el trading

### 1. **Interfaces web disponibles**:

- **Dashboard principal**: http://localhost:8000
- **Grafana (métricas)**: http://localhost:3000
  - Usuario: `admin`
  - Contraseña: `gridbot123`
- **Prometheus (datos)**: http://localhost:9090
- **Flower (tareas)**: http://localhost:5555

### 2. **Notificaciones por Telegram**:

Recibirás mensajes como:
```
🤖 GridBot - Nueva orden ejecutada
📈 Compra: 0.001 BTC a $45,000
💰 Ganancia: +$5.50
📊 Balance total: $1,250.75
```

### 3. **Comandos útiles**:

```bash
# Ver logs en tiempo real:
docker-compose logs -f api

# Ver estado de trading:
curl "http://localhost:8000/api/v1/metrics"

# Detener trading:
curl -X POST "http://localhost:8000/api/v1/trading/stop"

# Ver configuración:
curl "http://localhost:8000/api/v1/config"
```

### 4. **Monitoreo en Binance**:

1. **Ir a Binance** → **Cartera** → **Spot**
2. **Verificar que hay fondos**
3. **Ir a "Órdenes"** para ver operaciones
4. **Ir a "Historial"** para ver transacciones

---

## 🔧 Solución de problemas

### ❌ **Problema: "No se puede conectar a Binance"**

**Solución:**
1. Verificar que las API Keys son correctas
2. Verificar que Binance no está en mantenimiento
3. Verificar conexión a internet

```bash
# Verificar logs:
docker-compose logs api | grep -i binance
```

### ❌ **Problema: "No recibo mensajes de Telegram"**

**Solución:**
1. Verificar que el bot token es correcto
2. Verificar que el chat ID es correcto
3. Verificar que hiciste "Start" al bot

```bash
# Probar Telegram:
curl -X POST "http://localhost:8000/api/v1/test/telegram"
```

### ❌ **Problema: "No hay fondos suficientes"**

**Solución:**
1. Depositar más dinero en Binance
2. Verificar que tienes la criptomoneda correcta
3. Ajustar la cantidad por operación

### ❌ **Problema: "Los servicios no inician"**

**Solución:**
```bash
# Parar todo:
docker-compose down

# Limpiar volúmenes:
docker-compose down -v

# Reconstruir:
docker-compose build --no-cache

# Iniciar:
docker-compose up -d
```

### ❌ **Problema: "Error de permisos"**

**Solución:**
```bash
# Dar permisos a scripts:
chmod +x scripts/*.sh

# Verificar permisos de archivos:
ls -la .env
```

---

## 📚 Glosario de términos

| Término | Explicación |
|---------|-------------|
| **API Key** | Clave para conectar GridBot con Binance |
| **Bot** | Programa automatizado (como GridBot) |
| **BTC** | Bitcoin, la criptomoneda más popular |
| **ETH** | Ethereum, segunda criptomoneda más popular |
| **Exchange** | Plataforma para comprar/vender criptomonedas |
| **Grid Trading** | Estrategia de trading automático |
| **KYC** | Verificación de identidad en exchanges |
| **Order** | Orden de compra o venta |
| **P&L** | Profit & Loss (ganancias y pérdidas) |
| **Spot Trading** | Trading de criptomonedas reales |
| **Token** | Clave para conectar con Telegram |
| **Wallet** | Cartera digital para criptomonedas |

---

## 🎯 Consejos para principiantes

### ✅ **Haz esto:**
- Empieza con poco dinero ($50-100)
- Monitorea el sistema regularmente
- Lee las notificaciones de Telegram
- Mantén tus claves seguras
- Aprende sobre criptomonedas

### ❌ **No hagas esto:**
- Invertir más de lo que puedes perder
- Compartir tus claves con nadie
- Ignorar las notificaciones
- Dejar el sistema sin monitorear
- Operar sin entender los riesgos

### 📈 **Expectativas realistas:**
- **Ganancias**: 1-5% mensual (variable)
- **Riesgos**: Puedes perder dinero
- **Tiempo**: El sistema funciona 24/7
- **Esfuerzo**: Mínimo una vez configurado

---

## 🆘 Soporte y ayuda

### 📞 **Contacto:**
- **Email**: soporte@gridbot.com
- **Telegram**: @GridBotSupport
- **Documentación**: https://docs.gridbot.com

### 🔗 **Enlaces útiles:**
- **Binance**: https://www.binance.com
- **Telegram**: https://telegram.org
- **Docker**: https://www.docker.com

### 📖 **Recursos adicionales:**
- **Tutorial de Binance**: https://academy.binance.com
- **Guía de criptomonedas**: https://bitcoin.org
- **Trading básico**: https://www.investopedia.com

---

## 🎉 ¡Felicidades!

Si has llegado hasta aquí, ya tienes GridBot funcionando. Recuerda:

1. **Monitorea regularmente** el sistema
2. **Lee las notificaciones** de Telegram
3. **No inviertas más** de lo que puedes perder
4. **Aprende continuamente** sobre trading

¡Que tengas éxito con tu GridBot! 🚀

---

**Última actualización**: 27 de Julio, 2025  
**Versión**: 2.0.0  
**Autor**: GridBot Team 