#!/usr/bin/env python3
"""
Script de inicialización para configurar numba antes de importar vectorbt
"""

import os
import sys

def configure_numba_before_import():
    """Configura numba antes de que se importe vectorbt"""
    
    # Configurar variables de entorno críticas
    os.environ['NUMBA_DISABLE_CACHE'] = '1'
    os.environ['NUMBA_CACHE_DIR'] = '/dev/null'
    os.environ['NUMBA_DISABLE_JIT'] = '0'
    os.environ['NUMBA_DISABLE_CUDA'] = '1'
    os.environ['NUMBA_DISABLE_NVVM'] = '1'
    
    # Configurar numba directamente si está disponible
    try:
        import numba
        from numba.core.config import Config
        
        # Deshabilitar cache completamente
        config = Config()
        config.CACHE_DIR = '/dev/null'
        config.DISABLE_CACHE = True
        
        print("✅ Numba configurado con cache deshabilitado")
        
    except ImportError:
        print("⚠️  Numba no está disponible")
    except Exception as e:
        print(f"⚠️  Error configurando numba: {e}")

def safe_import_vectorbt():
    """Importa vectorbt de forma segura después de configurar numba"""
    try:
        # Configurar numba primero
        configure_numba_before_import()
        
        # Ahora importar vectorbt
        import vectorbt
        print(f"✅ VectorBT importado correctamente: {vectorbt.__version__}")
        return True
        
    except Exception as e:
        print(f"❌ Error importando VectorBT: {e}")
        return False

if __name__ == "__main__":
    print("🔧 Configurando Numba para VectorBT...")
    success = safe_import_vectorbt()
    
    if success:
        print("✅ Configuración completada exitosamente")
        sys.exit(0)
    else:
        print("❌ Error en la configuración")
        sys.exit(1)
