# 📁 Scripts de Utilidad - GridBot

Esta carpeta contiene todos los scripts de utilidad que no forman parte del funcionamiento normal del proyecto GridBot, pero son útiles para análisis, configuración y mantenimiento.

## 📋 **Índice de Scripts**

### **🔍 Scripts de Análisis y Verificación**

#### `verificar_activos_disponibles.py`
- **Propósito**: Verificar qué activos están disponibles en Binance
- **Uso**: Análisis inicial de activos para trading
- **Comando**: `python3 scripts/verificar_activos_disponibles.py`

#### `verificar_y_corregir_activos.py`
- **Propósito**: Verificar y corregir configuración de activos
- **Uso**: Validación de configuraciones antes de activar GridBot
- **Comando**: `python3 scripts/verificar_y_corregir_activos.py`

#### `verificar_requisitos_binance.py`
- **Propósito**: Verificar requisitos exactos de Binance para cada activo
- **Uso**: Análisis de filtros LOT_SIZE y NOTIONAL
- **Comando**: `python3 scripts/verificar_requisitos_binance.py`

### **⚙️ Scripts de Configuración**

#### `corregir_configuracion_activos.py`
- **Propósito**: Corregir configuración de activos basado en análisis
- **Uso**: Ajuste automático de parámetros de trading
- **Comando**: `python3 scripts/corregir_configuracion_activos.py`

#### `activar_gridbot_multi_activo.py`
- **Propósito**: Activar GridBot con configuración multi-activo
- **Uso**: Configuración final del sistema después de compras
- **Comando**: `python3 scripts/activar_gridbot_multi_activo.py`

### **💰 Scripts de Gestión de Capital**

#### `distribuir_usdt_para_activos.py`
- **Propósito**: Calcular distribución de USDT para activos
- **Uso**: Planificación de inversión en múltiples activos
- **Comando**: `python3 scripts/distribuir_usdt_para_activos.py`

#### `compras_manuales_activos.py`
- **Propósito**: Generar instrucciones de compras manuales
- **Uso**: Guía para compras manuales en Binance
- **Comando**: `python3 scripts/compras_manuales_activos.py`

### **🤖 Scripts de Compras Automáticas**

#### `compras_con_cantidades_corregidas.py`
- **Propósito**: Realizar compras con cantidades optimizadas
- **Uso**: Compras automáticas cumpliendo requisitos Binance
- **Comando**: `python3 scripts/compras_con_cantidades_corregidas.py`

#### `compras_con_api_existente.py`
- **Propósito**: Compras usando API existente del sistema
- **Uso**: Compras a través de la API del GridBot
- **Comando**: `python3 scripts/compras_con_api_existente.py`

#### `compras_binance_directo.py`
- **Propósito**: Compras directas con API de Binance
- **Uso**: Compras usando credenciales de Binance directamente
- **Comando**: `python3 scripts/compras_binance_directo.py`

#### `ejecutar_compras_automaticas.py`
- **Propósito**: Ejecutar compras automáticas con API secret
- **Uso**: Compras automáticas completas (requiere API secret)
- **Comando**: `python3 scripts/ejecutar_compras_automaticas.py`

#### `realizar_compras_automaticas.py`
- **Propósito**: Script principal para compras automáticas
- **Uso**: Orquestación completa del proceso de compras
- **Comando**: `python3 scripts/realizar_compras_automaticas.py`

### **🚀 Scripts de Optimización**

#### `optimize_project.py`
- **Propósito**: Optimización completa del proyecto GridBot
- **Uso**: Aplicar todas las optimizaciones al sistema
- **Comando**: `python3 scripts/optimize_project.py`

## 📊 **Flujo de Uso Recomendado**

### **1. Análisis Inicial**
```bash
python3 scripts/verificar_activos_disponibles.py
python3 scripts/verificar_requisitos_binance.py
```

### **2. Configuración**
```bash
python3 scripts/corregir_configuracion_activos.py
python3 scripts/distribuir_usdt_para_activos.py
```

### **3. Compras**
```bash
python3 scripts/compras_con_cantidades_corregidas.py
```

### **4. Activación**
```bash
python3 scripts/activar_gridbot_multi_activo.py
```

### **5. Optimización**
```bash
python3 scripts/optimize_project.py
```

## ⚠️ **Notas Importantes**

### **🔐 Seguridad**
- Los scripts que usan API de Binance requieren credenciales
- Nunca compartas tus API keys o secrets
- Usa solo scripts de fuentes confiables

### **📋 Prerrequisitos**
- Python 3.8+
- Dependencias instaladas (`pip install -r requirements.txt`)
- Configuración de Binance API
- Archivos de configuración del proyecto

### **🔄 Mantenimiento**
- Los scripts se actualizan según necesidades del proyecto
- Revisar documentación antes de usar scripts nuevos
- Hacer backup antes de ejecutar scripts de configuración

## 📁 **Archivos Generados**

Los scripts generan varios archivos de configuración y resultados:

- `grid_config_multi_activo_final.json` - Configuración final
- `distribucion_usdt_activos.json` - Distribución de capital
- `resultados_compras_*.json` - Resultados de compras
- `optimization_report.json` - Reporte de optimización
- `trading_history.json` - Historial de trading

## 🆘 **Soporte**

Si encuentras problemas con algún script:

1. Verifica que tienes todas las dependencias instaladas
2. Revisa los logs de error
3. Asegúrate de que la configuración es correcta
4. Consulta la documentación del proyecto principal

---

*Última actualización: 20 de Julio 2025*
*Versión: 2.0.0* 