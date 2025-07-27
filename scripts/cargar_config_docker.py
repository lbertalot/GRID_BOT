#!/usr/bin/env python3
"""
Script simplificado para cargar configuración del grid desde Docker
"""

import json
import os
from datetime import datetime

# Configuración de base de datos para Docker
os.environ['DATABASE_URL'] = 'postgresql://griduser:gridpass@db:5432/gridbot'

from app.db.session import SessionLocal
from app.models.grid_config import GridConfig
from app.models.asset_limit import AssetLimit

def cargar_configuracion():
    """Carga la configuración del grid"""
    
    print("🔄 Cargando configuración del grid...")
    
    # Leer el archivo de configuración
    config_file = "/app/grid_config_optimized.json"
    
    if not os.path.exists(config_file):
        print(f"❌ Error: No se encontró el archivo {config_file}")
        return False
    
    try:
        with open(config_file, 'r') as f:
            config_data = json.load(f)
    except Exception as e:
        print(f"❌ Error leyendo el archivo de configuración: {e}")
        return False
    
    db = SessionLocal()
    
    try:
        # Limpiar configuraciones existentes
        print("🧹 Limpiando configuraciones existentes...")
        db.query(GridConfig).delete()
        db.commit()
        
        # Cargar nuevas configuraciones
        print("📝 Cargando nuevas configuraciones...")
        
        configs_loaded = 0
        for symbol, config in config_data.items():
            if isinstance(config, dict):
                grid_config = GridConfig(
                    symbol=symbol,
                    min_price=config.get('lower_price', 0.0),
                    max_price=config.get('upper_price', 0.0),
                    grids=config.get('grid_levels', 5),
                    quantity=config.get('investment_amount', 0.001),
                    last_action="created"
                )
                db.add(grid_config)
                configs_loaded += 1
        
        db.commit()
        print(f"✅ {configs_loaded} configuraciones cargadas exitosamente")
        
        # Verificar la carga
        total_configs = db.query(GridConfig).count()
        
        print(f"📊 Total de configuraciones: {total_configs}")
        
        # Mostrar algunas configuraciones
        config_list = db.query(GridConfig).limit(5).all()
        if config_list:
            print("\n📋 Configuraciones cargadas:")
            for config in config_list:
                print(f"   - {config.symbol}: ${config.min_price:.4f} - ${config.max_price:.4f} ({config.grids} niveles)")
        
        return True
        
    except Exception as e:
        print(f"❌ Error cargando configuración: {e}")
        db.rollback()
        return False
    finally:
        db.close()

def verificar_asset_limits():
    """Verifica que los asset limits estén cargados"""
    
    print("\n🔍 Verificando asset limits...")
    
    db = SessionLocal()
    
    try:
        total_limits = db.query(AssetLimit).count()
        print(f"📊 Total de asset limits: {total_limits}")
        
        if total_limits > 0:
            # Mostrar algunos ejemplos
            sample_limits = db.query(AssetLimit).limit(5).all()
            print("\n📋 Ejemplos de asset limits:")
            for limit in sample_limits:
                print(f"   - {limit.symbol}: min_qty={limit.min_qty}, step_size={limit.step_size}")
        
        return total_limits > 0
        
    except Exception as e:
        print(f"❌ Error verificando asset limits: {e}")
        return False
    finally:
        db.close()

def main():
    """Función principal"""
    
    print("🚀 Cargando configuración del Grid Trading Bot")
    print("=" * 50)
    
    # Cargar configuración del grid
    if not cargar_configuracion():
        print("❌ Falló la carga de configuración")
        return
    
    # Verificar asset limits
    verificar_asset_limits()
    
    print("\n" + "=" * 50)
    print("✅ Carga de configuración completada")

if __name__ == "__main__":
    main() 