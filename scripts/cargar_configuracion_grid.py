#!/usr/bin/env python3
"""
Script para cargar la configuración del grid desde el archivo JSON a la base de datos
"""

import json
import sys
import os
from datetime import datetime

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import SessionLocal
from app.models.grid_config import GridConfig
from app.models.asset_limit import AssetLimit

def cargar_configuracion_grid():
    """Carga la configuración del grid desde el archivo JSON a la base de datos"""
    
    print("🔄 Cargando configuración del grid...")
    
    # Leer el archivo de configuración
    config_file = "grid_config_optimized.json"
    
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
        
        for symbol, config in config_data.items():
            if isinstance(config, dict) and 'is_active' in config:
                grid_config = GridConfig(
                    symbol=symbol,
                    is_active=config.get('is_active', False),
                    upper_price=config.get('upper_price', 0.0),
                    lower_price=config.get('lower_price', 0.0),
                    grid_levels=config.get('grid_levels', 0),
                    investment_amount=config.get('investment_amount', 0.0),
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                db.add(grid_config)
        
        db.commit()
        print(f"✅ Configuración cargada exitosamente")
        
        # Verificar la carga
        total_configs = db.query(GridConfig).count()
        print(f"📊 Total de configuraciones cargadas: {total_configs}")
        
        # Mostrar algunas configuraciones activas
        active_configs = db.query(GridConfig).filter(GridConfig.is_active == True).limit(5).all()
        if active_configs:
            print("\n📋 Configuraciones activas:")
            for config in active_configs:
                print(f"   - {config.symbol}: ${config.upper_price:.4f} - ${config.lower_price:.4f} ({config.grid_levels} niveles)")
        
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
    
    print("🚀 Iniciando carga de configuración del Grid Trading Bot")
    print("=" * 60)
    
    # Cargar configuración del grid
    if not cargar_configuracion_grid():
        print("❌ Falló la carga de configuración")
        sys.exit(1)
    
    # Verificar asset limits
    if not verificar_asset_limits():
        print("⚠️  No se encontraron asset limits")
    
    print("\n" + "=" * 60)
    print("✅ Carga de configuración completada exitosamente")
    print("\n🌐 URLs de acceso:")
    print("   - API: http://localhost:8000")
    print("   - Dashboard: http://localhost:8000/dashboard")
    print("   - API Docs: http://localhost:8000/docs")
    print("   - Prometheus: http://localhost:9090")
    print("   - Grafana: http://localhost:3000")

if __name__ == "__main__":
    main() 