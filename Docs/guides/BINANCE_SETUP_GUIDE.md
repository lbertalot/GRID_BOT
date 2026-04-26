# 🔐 Guía de Configuración de Binance API para GridBot

## 📋 **Tabla de Contenidos**

1. [Crear API Key](#crear-api-key)
2. [Configurar Permisos](#configurar-permisos)
3. [Configurar Restricciones de IP](#configurar-restricciones-de-ip)
4. [Verificar Configuración](#verificar-configuración)
5. [Solución de Problemas](#solución-de-problemas)
6. [Seguridad](#seguridad)

---

## 🔑 **Crear API Key**

### **Paso 1: Acceder a Binance**
1. Ve a **Binance.com**
2. Inicia sesión con tu cuenta
3. Ve a **Profile** (ícono de usuario en la esquina superior derecha)
4. Selecciona **API Management**

### **Paso 2: Crear Nueva API Key**
1. Haz clic en **Create API**
2. Selecciona **System generated** ✅
3. Completa la verificación de seguridad:
   - **2FA** (código de autenticación)
   - **Email** (código enviado a tu email)
   - **SMS** (si está habilitado)

### **Paso 3: Guardar Credenciales**
**⚠️ IMPORTANTE:** Las credenciales solo se muestran una vez

- **API Key:** Copia exactamente (64 caracteres)
- **Secret Key:** Copia exactamente (64 caracteres)
- **Guárdalas en un lugar seguro**

---

## ⚙️ **Configurar Permisos**

### **Configuración Recomendada para GridBot:**

#### **✅ ACTIVAR (Obligatorio):**
```
✅ IP Restrictions
✅ Enable Reading
✅ Enable Spot & Margin Trading
```

#### **❌ NO ACTIVAR (Por seguridad):**
```
❌ Enable Margin Loan, Repay & Transfer
❌ Enable Futures
❌ Permits Universal Transfer
❌ Enable Withdrawals
❌ Enable Symbol Whitelist
```

### **Explicación de Permisos:**

#### **🔒 IP Restrictions**
- **¿Qué hace?** Restringe el acceso solo a IPs específicas
- **¿Por qué activar?** Máxima seguridad
- **Configuración:** Agregar tu IP del servidor

#### **📖 Enable Reading**
- **¿Qué hace?** Permite leer balances, precios, órdenes
- **¿Por qué activar?** GridBot necesita leer datos
- **Obligatorio:** ✅ Sí

#### **💱 Enable Spot & Margin Trading**
- **¿Qué hace?** Permite ejecutar órdenes de compra/venta
- **¿Por qué activar?** GridBot ejecuta trades
- **Obligatorio:** ✅ Sí

#### **🚫 Enable Withdrawals**
- **¿Qué hace?** Permite retirar fondos
- **¿Por qué NO activar?** Riesgo de seguridad
- **Obligatorio:** ❌ No

---

## 🌐 **Configurar Restricciones de IP**

### **Paso 1: Obtener tu IP Pública**
```bash
# En tu servidor, ejecuta:
curl ifconfig.me
```

**Ejemplo de salida:**
```
143.105.135.105
```

### **Paso 2: Configurar en Binance**
1. En **API Management**, selecciona tu API Key
2. Ve a **Restrict Access**
3. Haz clic en **Add IP**
4. Agrega tu IP: `143.105.135.105`
5. Guarda los cambios

### **Paso 3: Verificar Configuración**
- **Estado:** Active
- **IPs autorizadas:** Solo tu IP del servidor
- **Sin restricciones:** Si no agregas IPs, cualquier IP puede acceder

---

## ✅ **Verificar Configuración**

### **Paso 1: Actualizar GridBot**
```bash
# Editar archivo .env
nano .env

# Agregar credenciales:
BINANCE_API_KEY=tu_api_key_aqui
BINANCE_API_SECRET=tu_api_secret_aqui
```

### **Paso 2: Reiniciar GridBot**
```bash
# Reiniciar contenedores
docker-compose restart api

# Verificar estado
docker-compose ps
```

### **Paso 3: Ejecutar Verificación**
```bash
# Verificar credenciales
docker-compose exec api python3 verify_binance_credentials.py
```

**Resultado esperado:**
```
✅ Credenciales válidas
Tipo de cuenta: SPOT
Permisos de trading: True
Balances con saldo: X
```

### **Paso 4: Verificar Funcionamiento**
```bash
# Verificar balances
curl http://localhost:8000/api/trade/balances

# Verificar precios
curl http://localhost:8000/api/trade/price/BNBUSDT
```

---

## 🛠️ **Solución de Problemas**

### **Error 1022: Signature Invalid**

#### **Causas Comunes:**
1. **API Secret incorrecto**
2. **IP no autorizada**
3. **API Key deshabilitada**
4. **Permisos insuficientes**

#### **Solución:**
```bash
# 1. Verificar credenciales
docker-compose exec api python3 verify_binance_credentials.py

# 2. Verificar IP
curl ifconfig.me

# 3. Verificar en Binance:
# - API Key activa
# - IP en lista blanca
# - Permisos correctos
```

### **Error 403: Forbidden**

#### **Causas:**
1. **IP no autorizada**
2. **API Key deshabilitada**
3. **Restricciones de IP activas**

#### **Solución:**
1. Verificar IP en Binance
2. Agregar IP a lista blanca
3. Verificar estado de API Key

### **Error 429: Rate Limit**

#### **Causas:**
1. **Demasiadas solicitudes**
2. **Límite de API excedido**

#### **Solución:**
1. Reducir frecuencia de solicitudes
2. Implementar retry con backoff
3. Usar websockets para datos en tiempo real

---

## 🔒 **Seguridad**

### **Mejores Prácticas:**

#### **1. API Keys**
- ✅ **No compartir** credenciales
- ✅ **Usar restricciones de IP**
- ✅ **Permisos mínimos**
- ✅ **Rotar regularmente**

#### **2. IP Restrictions**
- ✅ **Solo IP del servidor**
- ✅ **No usar 0.0.0.0/0**
- ✅ **Verificar IP regularmente**

#### **3. Permisos**
- ✅ **Solo lo necesario**
- ❌ **Nunca Enable Withdrawals**
- ✅ **Revisar regularmente**

### **Verificación Regular:**
```bash
# Verificar credenciales
docker-compose exec api python3 verify_binance_credentials.py

# Verificar logs
docker-compose logs api | grep -i "binance"

# Verificar métricas
curl http://localhost:8000/api/metrics/metrics/
```

---

## 📊 **Monitoreo**

### **Métricas Importantes:**
- **`binance_connection_status`:** Estado de conexión
- **`binance_api_requests_total`:** Total de solicitudes
- **`binance_api_errors_total`:** Total de errores
- **`binance_response_time`:** Tiempo de respuesta

### **Alertas Recomendadas:**
- **Conexión perdida**
- **Errores de API**
- **Rate limit excedido**
- **Cambios de balance**

---

## 🎯 **Configuración Final**

### **Estado Óptimo:**
```
✅ API Key: System Generated
✅ IP Restrictions: 143.105.135.105
✅ Enable Reading: Activado
✅ Enable Spot & Margin Trading: Activado
❌ Enable Withdrawals: Desactivado
✅ Estado: Active
```

### **Verificación Final:**
```bash
# 1. Verificar credenciales
docker-compose exec api python3 verify_binance_credentials.py

# 2. Verificar balances
curl http://localhost:8000/api/trade/balances

# 3. Verificar precios
curl http://localhost:8000/api/trade/price/BNBUSDT

# 4. Verificar métricas
curl http://localhost:8000/api/metrics/metrics/
```

---

## 📞 **Soporte**

### **Comandos Útiles:**
```bash
# Verificar estado de API
docker-compose exec api python3 check_api_key_status.py

# Ver logs de Binance
docker-compose logs api | grep -i "binance"

# Verificar conectividad
docker-compose exec api ping api.binance.com
```

### **Recursos:**
- **Documentación Binance:** https://binance-docs.github.io/apidocs/
- **API Status:** https://status.binance.com/
- **Support:** https://support.binance.com/

---

**🎉 ¡Configuración de Binance completada!**

GridBot está listo para operar con tu cuenta de Binance de forma segura.
