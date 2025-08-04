#!/usr/bin/env python3
"""
Script para recargar la configuración del grid manager
"""

import asyncio
import sys
import os
from dotenv import load_dotenv

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Cargar variables de entorno
load_dotenv()

async def reload_config():
    """Recarga la configuración del grid manager"""
    try:
        print("🔄 Recargando configuración del grid manager...")
        
        from app.core.optimized_grid_manager import create_optimized_grid_manager
        
        # Crear nuevo manager con la configuración actualizada
        manager = await create_optimized_grid_manager('grid_config_optimized.json')
        
        if manager:
            print("✅ Configuración recargada exitosamente")
            
            # Mostrar la configuración actual
            print("\n📊 Configuración actual:")
            for symbol, config in manager.config.assets.items():
                print(f"   {symbol}:")
                print(f"     Rango: ${config.min_price} - ${config.max_price}")
                print(f"     Grids: {config.grids}")
                print(f"     Cantidad: {config.quantity}")
                print(f"     Activo: {config.is_active}")
                print(f"     Niveles: {config.grid_levels}")
                print()
        else:
            print("❌ Error recargando configuración")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(reload_config()) 