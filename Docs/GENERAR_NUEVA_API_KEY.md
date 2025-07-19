# 🔑 Guía para Generar Nueva API Key de Binance

## 📋 **Pasos para Crear Nueva API Key**

### **1. 🔐 Acceder a Binance**
1. Ve a **Binance.com**
2. Inicia sesión con tu cuenta
3. Ve a **Profile** → **API Management**

### **2. 🗑️ Eliminar API Key Actual (Opcional)**
1. Selecciona la API Key actual
2. Haz clic en **Delete**
3. Confirma la eliminación

### **3. ➕ Crear Nueva API Key**
1. Haz clic en **Create API**
2. Completa la verificación de seguridad (2FA, email, etc.)
3. **IMPORTANTE:** Guarda el **API Key** y **Secret Key** inmediatamente
4. **NO LOS PIERDAS** - Solo se muestran una vez

### **4. ⚙️ Configurar Permisos**
Configura los siguientes permisos:

#### **Permisos Obligatorios:**
- ✅ **Read Info** (obligatorio)
- ✅ **Enable Trading** (para trading real)

#### **Permisos Opcionales:**
- ⚪ **Enable Futures** (si usas futuros)
- ⚪ **Enable Withdrawals** (solo si necesitas retirar)

### **5. 🌐 Configurar Restricciones de IP (Recomendado)**
1. Ve a **Restrict Access**
2. Agrega tu IP actual: `2803:9810:8461:6b10:fcfb:3104:41f1:87d2`
3. O desactiva temporalmente las restricciones para pruebas

### **6. 📝 Actualizar GridBot**
1. Abre el archivo `.env`
2. Reemplaza las credenciales:

```env
# Binance API (configura con tus valores reales)
BINANCE_API_KEY=tu_nueva_api_key_aqui
BINANCE_API_SECRET=tu_nuevo_api_secret_aqui
```

### **7. 🔄 Reiniciar GridBot**
```bash
docker-compose restart api
```

### **8. ✅ Verificar**
```bash
# Ejecutar verificación
docker-compose exec api python3 verify_binance_credentials.py

# Verificar logs
docker-compose logs api | grep -i "binance"
```

## ⚠️ **Consideraciones de Seguridad**

### **🔒 Mejores Prácticas:**
- ✅ Usa restricciones de IP
- ✅ Limita los permisos al mínimo necesario
- ✅ No compartas las credenciales
- ✅ Usa 2FA en tu cuenta de Binance
- ✅ Revisa regularmente el uso de la API

### **🚨 Advertencias:**
- ❌ Nunca compartas tu API Secret
- ❌ No uses la misma API Key en múltiples aplicaciones
- ❌ No guardes las credenciales en código público
- ❌ No uses permisos de retiro a menos que sea necesario

## 🎯 **Verificación Final**

Después de crear la nueva API Key, deberías ver:

### **En los logs:**
```
✅ Cliente de Binance inicializado correctamente
   Tipo de cuenta: SPOT
```

### **En Telegram:**
```
✅ GridBot conectado a Binance
📊 Trading real habilitado
💰 Balance: $X,XXX.XX
```

### **En las métricas:**
```
gridbot_binance_connection_status 1.0
```

## 📞 **Soporte**

Si tienes problemas:
1. Verifica que la API Key esté **Active**
2. Confirma que los permisos sean correctos
3. Verifica que tu IP esté en la lista blanca
4. Ejecuta el script de verificación
5. Revisa los logs de GridBot

---

**🎉 Una vez que tengas la nueva API Key, GridBot funcionará en modo real con todas las funcionalidades.** 