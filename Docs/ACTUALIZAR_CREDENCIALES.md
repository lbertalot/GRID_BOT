# 🔧 Guía para Actualizar Credenciales de Binance

## 🎯 **Problema Detectado**

El API Secret actual tiene caracteres extra al final (`%`), lo que causa el error 1022.

## 📋 **Pasos para Solucionar**

### **1. 🔐 Obtener Credenciales Correctas**

#### **Opción A: Verificar API Key Actual**
1. Ve a **Binance.com** → **Profile** → **API Management**
2. Selecciona tu API Key actual
3. Haz clic en **View** para ver el API Secret
4. **Copia exactamente** el API Secret (debe tener 64 caracteres)

#### **Opción B: Crear Nueva API Key (Recomendado)**
1. Ve a **Binance.com** → **Profile** → **API Management**
2. Haz clic en **Create API**
3. Completa la verificación de seguridad
4. **IMPORTANTE:** Guarda inmediatamente el API Key y Secret Key
5. Configura permisos:
   - ✅ **Read Info**
   - ✅ **Enable Trading**
6. Agrega tu IP `143.105.135.105` a la lista blanca

### **2. 📝 Actualizar Archivo .env**

Abre el archivo `.env` y actualiza las credenciales:

```env
# Binance API (reemplaza con tus credenciales correctas)
BINANCE_API_KEY=tu_api_key_aqui_sin_espacios
BINANCE_API_SECRET=tu_api_secret_aqui_sin_espacios_ni_caracteres_extra
```

### **3. ✅ Verificar Formato**

**API Key debe tener:** 64 caracteres
**API Secret debe tener:** 64 caracteres

**Ejemplo correcto:**
```env
BINANCE_API_KEY=9JPgJFkYql7shuym5B25H4xdyacZRXv3luXCAaJhJigILFqn0BQrq7AbDvMcKEOQ
BINANCE_API_SECRET=S9EcVwr8LQWI4epJSs8x3uoj4za8gqfNEgBkBJWPXVuw8gci7YZn6av8dhpkqBXZ
```

**❌ Incorrecto (con % al final):**
```env
BINANCE_API_SECRET=S9EcVwr8LQWI4epJSs8x3uoj4za8gqfNEgBkBJWPXVuw8gci7YZn6av8dhpkqBXZ%
```

### **4. 🔄 Reiniciar GridBot**

```bash
# Reiniciar el contenedor
docker-compose restart api

# Verificar logs
docker-compose logs api | grep -i "binance"
```

### **5. ✅ Verificar Funcionamiento**

```bash
# Ejecutar verificación
docker-compose exec api python3 verify_binance_credentials.py

# Verificar estado detallado
docker-compose exec api python3 check_api_key_status.py
```

## 🎯 **Resultado Esperado**

### **✅ Si funciona correctamente:**
```
✅ API Key válida!
Tipo de cuenta: SPOT
Permisos de trading: true
```

### **✅ En los logs de GridBot:**
```
✅ Cliente de Binance inicializado correctamente
📊 Trading real habilitado
```

### **✅ En Telegram:**
```
✅ GridBot conectado a Binance
💰 Balance: $X,XXX.XX
```

## ⚠️ **Consideraciones Importantes**

### **🔒 Seguridad:**
- ✅ Copia las credenciales exactamente sin espacios
- ✅ No agregues caracteres extra
- ✅ Verifica que tengan la longitud correcta
- ✅ No compartas las credenciales

### **🌐 IP Autorizada:**
- ✅ Tu IP `143.105.135.105` ya está en la lista blanca
- ✅ No necesitas cambiar la configuración de IP

### **⏰ Tiempo de Propagación:**
- ⏳ Los cambios pueden tardar 1-2 minutos en propagarse
- ⏳ Si no funciona inmediatamente, espera un poco y vuelve a probar

## 🆘 **Si el Problema Persiste**

1. **Verifica el estado de la API Key** en Binance
2. **Confirma los permisos** configurados
3. **Verifica que la IP** esté correctamente autorizada
4. **Ejecuta los scripts de diagnóstico** para más información

---

**🎉 Una vez corregidas las credenciales, GridBot funcionará en modo real con todas las funcionalidades.** 