#!/usr/bin/env python3
"""
Script rápido para verificar la configuración
"""

import json

def check_config():
    try:
        with open("grid_config_optimized.json", 'r') as f:
            config = json.load(f)
        
        print("✅ Configuración cargada exitosamente")
        print(f"Versión: {config.get('_safe_config_metadata', {}).get('version', 'N/A')}")
        print(f"Estado: {config.get('_safe_config_metadata', {}).get('status', 'N/A')}")
        
        system_config = config.get('system_config', {})
        print(f"System ready: {system_config.get('system_ready', 'N/A')}")
        print(f"Fase: {system_config.get('phase', 'N/A')}")
        print(f"Trading mode: {system_config.get('trading_mode', 'N/A')}")
        
        btc_config = config.get('BTCUSDT', {})
        print(f"BTCUSDT activado: {btc_config.get('phase8_activated', 'N/A')}")
        print(f"BTCUSDT trading mode: {btc_config.get('trading_mode', 'N/A')}")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    check_config()
