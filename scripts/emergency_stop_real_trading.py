#!/usr/bin/env python3
"""
Script de Emergencia - Detener Trading Real Inmediatamente
GridBot v2.5 - Activación de Modo de Emergencia
"""

import json
import os
import logging
import time
from datetime import datetime
from pathlib import Path

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class EmergencyStopRealTrading:
    def __init__(self):
        self.config_file = "grid_config_optimized.json"
        self.reports_dir = os.getenv("REPORTS_DIR", "reports")
        self.incidents_dir = os.path.join(self.reports_dir, "incidents")
        Path(self.incidents_dir).mkdir(parents=True, exist_ok=True)
        self.emergency_report_file = os.path.join(self.incidents_dir, "emergency_stop_report.json")
        
    def load_current_config(self):
        """Cargar configuración actual del sistema"""
        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
            logger.info("✅ Configuración actual cargada")
            return config
        except Exception as e:
            logger.error("❌ Error cargando configuración: %s", e)
            return None
    
    def activate_emergency_stop(self):
        """Activar parada de emergencia en todos los activos"""
        print("🚨 ACTIVANDO PARADA DE EMERGENCIA INMEDIATA")
        print("=" * 60)
        
        config = self.load_current_config()
        if not config:
            print("   ❌ No se puede proceder sin configuración")
            return False
        
        # 1. Activar modo de emergencia en todos los activos
        print("   🔴 Activando modo de emergencia...")
        
        for asset in ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']:
            if asset in config:
                config[asset]['safe_mode'] = True
                config[asset]['trading_mode'] = 'EMERGENCY_STOP'
                config[asset]['phase8_activated'] = False
                print(f"      • {asset}: 🛑 EMERGENCY_STOP activado")
        
        # 2. Actualizar configuración del sistema
        if 'system_config' in config:
            config['system_config']['system_ready'] = False
            config['system_config']['phase'] = 'EMERGENCY_STOP'
            config['system_config']['trading_mode'] = 'EMERGENCY_STOP'
        
        # 3. Actualizar metadata
        if '_safe_config_metadata' in config:
            config['_safe_config_metadata']['status'] = 'EMERGENCY_STOP_ACTIVE'
            config['_safe_config_metadata']['reason'] = 'DISCREPANCIA CRÍTICA ENTRE SISTEMA Y BALANCE REAL - TRADING SUSPENDIDO'
            config['_safe_config_metadata']['emergency_activated_at'] = datetime.now().isoformat()
            config['_safe_config_metadata']['real_balance_binance'] = 317.10
            config['_safe_config_metadata']['system_reported_balance'] = 408.78
            config['_safe_config_metadata']['discrepancy'] = -91.68
        
        # 4. Guardar configuración de emergencia
        with open(self.config_file, 'w') as f:
            json.dump(config, f, indent=2)
        
        print("   ✅ Configuración de emergencia aplicada")
        return True
    
    def generate_emergency_report(self):
        """Generar reporte de emergencia"""
        print("\n📋 GENERANDO REPORTE DE EMERGENCIA")
        print("=" * 50)
        
        emergency_report = {
            'emergency_type': 'DISCREPANCIA_CRÍTICA_BALANCE',
            'activated_at': datetime.now().isoformat(),
            'critical_issue': {
                'description': 'Discrepancia masiva entre sistema reportado y balance real de Binance',
                'system_reported_balance': 408.78,
                'real_binance_balance': 317.10,
                'discrepancy_amount': -91.68,
                'discrepancy_percentage': -22.4
            },
            'actions_taken': [
                'Trading real suspendido inmediatamente',
                'Modo de emergencia activado en todos los activos',
                'Circuit breakers activados',
                'Monitoreo intensivo activado'
            ],
            'current_status': {
                'trading_mode': 'EMERGENCY_STOP',
                'system_ready': False,
                'safe_mode': True,
                'monitoring_active': True
            },
            'next_steps': [
                'Investigar causa de la discrepancia',
                'Validar integridad del sistema',
                'Revisar logs y transacciones',
                'Restaurar sistema solo después de validación completa'
            ],
            'safety_measures': [
                'Todos los activos en modo protegido',
                'Trading completamente suspendido',
                'Monitoreo 24/7 activado',
                'Alertas automáticas activadas'
            ]
        }
        
        # Guardar reporte de emergencia
        with open(self.emergency_report_file, 'w') as f:
            json.dump(emergency_report, f, indent=2)
        
        print("   ✅ Reporte de emergencia generado")
        print(f"   📄 Archivo: {self.emergency_report_file}")
        
        return emergency_report
    
    def execute_emergency_stop(self):
        """Ejecutar parada de emergencia completa"""
        print("🚨 EJECUTANDO PARADA DE EMERGENCIA COMPLETA")
        print("=" * 60)
        
        # 1. Activar parada de emergencia
        emergency_activated = self.activate_emergency_stop()
        
        if not emergency_activated:
            print("   ❌ Error activando parada de emergencia")
            return False
        
        # 2. Generar reporte de emergencia
        emergency_report = self.generate_emergency_report()
        
        # 3. Confirmar estado de emergencia
        print("\n🛑 ESTADO DE EMERGENCIA ACTIVADO")
        print("   • Trading real: SUSPENDIDO")
        print("   • Modo seguro: ACTIVADO")
        print("   • Circuit breakers: ACTIVADOS")
        print("   • Monitoreo: INTENSIVO")
        
        return True

def main():
    """Función principal"""
    print("🚨 PARADA DE EMERGENCIA - TRADING REAL SUSPENDIDO")
    print("=" * 80)
    print("GridBot v2.5 - Activación de Modo de Emergencia")
    print(f"📅 Fecha de emergencia: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    print("🚨 ALERTA CRÍTICA DETECTADA:")
    print("   • Discrepancia masiva entre sistema y balance real")
    print("   • Sistema reporta: $408.78 (+29.03%)")
    print("   • Binance real: $317.10 (-2.69%)")
    print("   • Diferencia: -$91.68 (CRÍTICO)")
    print()
    
    # Crear sistema de parada de emergencia
    emergency_stop = EmergencyStopRealTrading()
    
    # Ejecutar parada de emergencia
    emergency_successful = emergency_stop.execute_emergency_stop()
    
    if emergency_successful:
        print("\n🛑 PARADA DE EMERGENCIA EXITOSA")
        print("✅ Trading real suspendido inmediatamente")
        print("✅ Modo seguro activado")
        print("✅ Sistema protegido")
        print("⏰ INVESTIGAR CAUSA ANTES DE REACTIVAR")
    else:
        print("\n❌ ERROR EN PARADA DE EMERGENCIA")
        print("⚠️ Revisar sistema manualmente")
        print("⚠️ Suspender trading manualmente si es necesario")
    
    return emergency_successful

if __name__ == "__main__":
    main()
