# 🔧 Solución del Error 1022 de Binance API

## 📋 **Descripción del Error**

**Código:** -1022  
**Mensaje:** "Signature for this request is not valid"  
**Causa:** Problema con la firma de la API de Binance

## 🔍 **Diagnóstico Confirmado**

El error 1022 indica que las credenciales de Binance no son válidas o tienen algún problema de configuración.

## ✅ **Soluciones Paso a Paso**

### **1. 🔑 Verificar API Key y Secret**

#### **En Binance:**
1. Ve a **Binance.com** → **Profile** → **API Management**
2. Verifica que tu API Key esté **activa**
3. Copia la **API Key** y **Secret Key** exactamente

#### **En GridBot:**
1. Abre el archivo `.env`
2. Verifica que las credenciales estén correctas:

```env
BINANCE_API_KEY=tu_api_key_aqui
BINANCE_API_SECRET=tu_api_secret_aqui
```

**⚠️ Importante:**
- No incluyas espacios extra
- No incluyas comillas
- Copia exactamente desde Binance

### **2. 🚫 Verificar Permisos de API Key**

#### **Permisos Requeridos:**
- ✅ **Read Info** (obligatorio)
- ✅ **Enable Trading** (para trading real)
- ✅ **Enable Futures** (si usas futuros)

#### **Cómo verificar:**
1. Ve a **Binance.com** → **Profile** → **API Management**
2. Selecciona tu API Key
3. Verifica que tenga los permisos necesarios
4. Si no los tiene, **edita** la API Key y agrega los permisos

### **3. 🌐 Verificar Restricciones de IP**

#### **Problema común:**
- Binance puede tener restricciones de IP
- Solo permite conexiones desde IPs autorizadas

#### **Solución:**
1. Ve a **Binance.com** → **Profile** → **API Management**
2. Selecciona tu API Key
3. Ve a **Restrict Access**
4. Agrega tu IP actual a la lista blanca
5. O desactiva las restricciones de IP (menos seguro)

#### **Para obtener tu IP:**
```bash
curl ifconfig.me
```

### **4. ⚠️ Verificar Estado de la API Key**

#### **Estados posibles:**
- ✅ **Active** - Funcionando
- ❌ **Disabled** - Deshabilitada
- ⏸️ **Paused** - Pausada

#### **Solución:**
1. Ve a **Binance.com** → **Profile** → **API Management**
2. Verifica que el estado sea **Active**
3. Si está deshabilitada, **habilítala**

### **5. 🔄 Verificar Sincronización de Tiempo**

#### **Problema:**
- Los timestamps deben estar sincronizados con Binance
- Diferencias de tiempo pueden causar errores de firma

#### **Solución:**
```bash
# Verificar tiempo del sistema
date

# Sincronizar con servidor NTP
sudo ntpdate -s time.nist.gov
```

### **6. 🧪 Crear Nueva API Key (Si todo falla)**

#### **Pasos:**
1. Ve a **Binance.com** → **Profile** → **API Management**
2. **Elimina** la API Key actual
3. **Crea** una nueva API Key
4. Configura los permisos necesarios
5. Actualiza el archivo `.env` con las nuevas credenciales

## 🔧 **Solución Temporal: Modo Simulación**

### **GridBot ya incluye modo simulación automático:**

Cuando detecta el error 1022, GridBot automáticamente:
- ✅ Activa el modo simulación
- ✅ Permite probar todas las funcionalidades
- ✅ Registra métricas simuladas
- ✅ Envía alertas de Telegram

### **Ventajas del modo simulación:**
- 🧪 Pruebas sin riesgo
- 📊 Métricas completas
- 🔄 Funcionalidad completa
- 📱 Alertas de Telegram funcionando

## 🚀 **Verificación de la Solución**

### **1. Ejecutar script de verificación:**
```bash
docker-compose exec api python3 verify_binance_credentials.py
```

### **2. Verificar logs de GridBot:**
```bash
docker-compose logs api | grep -i "binance"
```

### **3. Probar endpoint de trading:**
```bash
curl -H "Authorization: Bearer gridbot_api_key_2024_secure_12345" \
     http://localhost:8000/api/trade/price/BTCUSDT
```

## 📱 **Alertas de Telegram**

### **Mensajes que recibirás:**

#### **Error 1022:**
```
🚨 Error en GridBot Trading API
❌ Error code = 1022
🔧 Activando modo simulación
```

#### **Modo simulación activo:**
```
🔄 GridBot en modo simulación
📊 Funcionalidad completa disponible
🔧 Credenciales de Binance inválidas
```

#### **Credenciales válidas:**
```
✅ GridBot conectado a Binance
📊 Trading real habilitado
💰 Balance: $X,XXX.XX
```

## 🎯 **Resumen de Acciones**

### **Inmediato:**
1. ✅ GridBot funciona en modo simulación
2. ✅ Todas las funcionalidades disponibles
3. ✅ Métricas y alertas funcionando

### **Para trading real:**
1. 🔑 Verificar credenciales en Binance
2. 🚫 Configurar permisos correctos
3. 🌐 Verificar restricciones de IP
4. 🔄 Actualizar archivo `.env`
5. 🚀 Reiniciar GridBot

## 📞 **Soporte**

Si necesitas ayuda adicional:
1. Revisa los logs: `docker-compose logs api`
2. Ejecuta el diagnóstico: `python3 verify_binance_credentials.py`
3. Verifica el estado en Grafana: http://localhost:3000

---

**🎉 GridBot está funcionando correctamente en modo simulación mientras solucionas las credenciales de Binance.** 