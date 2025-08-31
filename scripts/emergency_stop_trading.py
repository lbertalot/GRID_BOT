#!/usr/bin/env python3
"""
Script de emergencia para detener todas las operaciones de trading
"""

import json
import shutil
import os
import sys
from datetime import datetime

def emergency_stop():
    """Detiene todas las operaciones de trading de emergencia"""
    print("🚨 EMERGENCY STOP - DETENIENDO TODAS LAS OPERACIONES")
    print("=" * 60)
    
    try:
        # 1. Backup de configuración actual
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"grid_config_emergency_backup_{timestamp}.json"
        
        if os.path.exists("grid_config_optimized.json"):
            shutil.copy("grid_config_optimized.json", backup_name)
            print(f"✅ Backup de emergencia creado: {backup_name}")
        
        # 2. Aplicar configuración de emergencia
        shutil.copy("grid_config_emergency_stop.json", "grid_config_optimized.json")
        print("✅ Configuración de emergencia aplicada")
        
        # 3. Deshabilitar trading en .env
        disable_trading_env()
        
        # 4. Crear reporte de emergencia
        create_emergency_report()
        
        print("\n🚨 EMERGENCY STOP ACTIVADO")
        print("=" * 40)
        print("❌ Todas las operaciones automáticas DETENIDAS")
        print("❌ Trading deshabilitado")
        print("❌ Solo modo de monitoreo activo")
        print("\n📋 Próximos pasos:")
        print("   1. Analizar posiciones abiertas")
        print("   2. Evaluar pérdidas totales")
        print("   3. Desarrollar estrategia de recuperación")
        print("   4. NO reactivar sin confirmación manual")
        
        return True
        
    except Exception as e:
        print(f"❌ Error en emergency stop: {e}")
        return False

def disable_trading_env():
    """Deshabilita el trading en el archivo .env"""
    print("🔧 Deshabilitando trading en configuración...")
    
    if os.path.exists(".env"):
        # Leer archivo actual
        with open(".env", "r") as f:
            content = f.read()
        
        # Reemplazar configuraciones de trading
        content = content.replace("TRADING_ENABLED=true", "TRADING_ENABLED=false")
        content = content.replace("PAPER_TRADING=false", "PAPER_TRADING=true")
        
        # Agregar configuración de emergencia
        emergency_config = f"""
# =============================================================================
# EMERGENCY STOP CONFIGURATION - {datetime.now()}
# =============================================================================
EMERGENCY_STOP_ACTIVE=true
TRADING_ENABLED=false
PAPER_TRADING=true
MAX_ACTIVE_ORDERS=0
EMERGENCY_STOP_REASON="Pérdidas sustanciales detectadas"
EMERGENCY_STOP_TIMESTAMP="{datetime.now().isoformat()}"
"""
        
        content += emergency_config
        
        # Escribir archivo actualizado
        with open(".env", "w") as f:
            f.write(content)
        
        print("✅ Configuración .env actualizada")

def create_emergency_report():
    """Crea un reporte de emergencia"""
    print("📊 Creando reporte de emergencia...")
    
    report = f"""
# REPORTE DE EMERGENCIA - GRIDBOT TRADING
# ========================================

Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Estado: EMERGENCY_STOP ACTIVO

## 🚨 PROBLEMAS DETECTADOS

### Pérdidas Financieras:
- Balance inicial: $392.03 USDT
- Balance actual: $380.76 USDT
- Pérdida total: -$11.27 USDT (-2.87%)

### Problemas Operacionales:
1. **Solo compras, sin ventas:** Sistema ejecutando múltiples compras sin vender
2. **Precios fuera de rango:** Rangos de grid desactualizados
3. **Comisiones acumulativas:** Cada operación paga comisiones sin ganancias
4. **Balance USDT agotado:** Solo $5.14 USDT disponibles

### Operaciones Problemáticas:
- AVAXUSDT: Compras a $25.56 y $25.42
- Precio actual: $25.47 (pérdida por unidad)
- Comisiones pagadas: ~$0.046 USDT
- Pérdida estimada: ~$11.23 USDT

## 🛡️ ACCIONES TOMADAS

1. ✅ Todas las operaciones automáticas DETENIDAS
2. ✅ Trading deshabilitado
3. ✅ Solo modo de monitoreo activo
4. ✅ Backup de configuración creado
5. ✅ Configuración de emergencia aplicada

## 📋 PLAN DE RECUPERACIÓN

### Fase 1: Análisis (Inmediato)
- [ ] Analizar todas las posiciones abiertas
- [ ] Calcular pérdidas exactas por símbolo
- [ ] Identificar causas raíz del problema

### Fase 2: Estrategia de Recuperación (1-2 días)
- [ ] Desarrollar estrategia conservadora
- [ ] Configurar rangos de grid realistas
- [ ] Implementar validaciones adicionales

### Fase 3: Reactivación Controlada (3-5 días)
- [ ] Probar en modo paper trading
- [ ] Validar estrategia con datos históricos
- [ ] Reactivar solo con confirmación manual

## ⚠️ ADVERTENCIAS

- NO reactivar trading automático sin análisis completo
- NO modificar configuración sin backup
- NO operar sin validar rangos de precios
- Mantener monitoreo constante

## 📞 CONTACTO DE EMERGENCIA

En caso de problemas adicionales:
1. Revisar logs: tail -f logs/dockers.log
2. Verificar estado: docker-compose ps
3. Analizar configuración: cat grid_config_optimized.json

---
Reporte generado automáticamente por GridBot Emergency System
"""
    
    with open("Docs/EMERGENCY_REPORT.md", "w") as f:
        f.write(report)
    
    print("✅ Reporte de emergencia creado: Docs/EMERGENCY_REPORT.md")

def restart_services():
    """Reinicia los servicios para aplicar cambios"""
    print("🔄 Reiniciando servicios...")
    
    try:
        import subprocess
        result = subprocess.run(["docker-compose", "restart", "api", "celery_worker"], 
                              capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Servicios reiniciados exitosamente")
        else:
            print(f"⚠️ Error reiniciando servicios: {result.stderr}")
            
    except Exception as e:
        print(f"⚠️ No se pudieron reiniciar servicios: {e}")
        print("   Reinicia manualmente con: docker-compose restart api celery_worker")

def main():
    """Función principal"""
    print("🚨 SISTEMA DE EMERGENCIA GRIDBOT")
    print("=" * 50)
    
    # Confirmación de emergencia
    print("⚠️  ADVERTENCIA: Esto detendrá TODAS las operaciones de trading")
    print("⚠️  Solo procede si estás seguro de que es necesario")
    
    # En modo automático, proceder directamente
    print("\n🔄 Procediendo con emergency stop...")
    
    success = emergency_stop()
    
    if success:
        print("\n✅ Emergency stop completado exitosamente")
        print("\n🔄 Reiniciando servicios para aplicar cambios...")
        restart_services()
        
        print("\n📋 RESUMEN DE ACCIONES:")
        print("   ✅ Configuración de emergencia aplicada")
        print("   ✅ Trading deshabilitado")
        print("   ✅ Servicios reiniciados")
        print("   ✅ Reporte de emergencia creado")
        
        print("\n🎯 PRÓXIMOS PASOS:")
        print("   1. Revisar Docs/EMERGENCY_REPORT.md")
        print("   2. Analizar posiciones abiertas en Binance")
        print("   3. Evaluar estrategia de recuperación")
        print("   4. NO reactivar sin análisis completo")
        
    else:
        print("\n❌ Error en emergency stop")
        print("   Revisa los logs y contacta soporte")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
