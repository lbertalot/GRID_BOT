#!/usr/bin/env python3
"""
Script para configurar numba correctamente en Docker
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path

def setup_numba_cache():
    """Configura numba para evitar problemas de cache en Docker"""
    
    # Crear directorio de cache temporal
    cache_dir = "/tmp/numba_cache"
    os.makedirs(cache_dir, exist_ok=True)
    
    # Configurar variables de entorno
    os.environ['NUMBA_CACHE_DIR'] = cache_dir
    os.environ['NUMBA_DISABLE_JIT'] = '0'
    os.environ['NUMBA_DISABLE_CUDA'] = '1'
    os.environ['NUMBA_DISABLE_NVVM'] = '1'
    
    # Configurar numba para usar cache temporal
    try:
        import numba
        from numba.core.config import Config
        
        # Configurar numba para usar cache temporal
        config = Config()
        config.CACHE_DIR = cache_dir
        
        print(f"✅ Numba configurado correctamente")
        print(f"   Cache directory: {cache_dir}")
        print(f"   JIT enabled: {not bool(os.environ.get('NUMBA_DISABLE_JIT', '0'))}")
        print(f"   CUDA disabled: {bool(os.environ.get('NUMBA_DISABLE_CUDA', '1'))}")
        
    except ImportError:
        print("⚠️  Numba no está instalado")
    except Exception as e:
        print(f"⚠️  Error configurando numba: {e}")

def test_vectorbt_import():
    """Prueba la importación de vectorbt"""
    try:
        import vectorbt
        print(f"✅ VectorBT importado correctamente: {vectorbt.__version__}")
        return True
    except Exception as e:
        print(f"❌ Error importando VectorBT: {e}")
        return False

def test_numba_import():
    """Prueba la importación de numba"""
    try:
        import numba
        print(f"✅ Numba importado correctamente: {numba.__version__}")
        return True
    except Exception as e:
        print(f"❌ Error importando Numba: {e}")
        return False

if __name__ == "__main__":
    print("🔧 Configurando Numba para Docker...")
    
    # Configurar numba
    setup_numba_cache()
    
    # Probar importaciones
    print("\n🧪 Probando importaciones...")
    numba_ok = test_numba_import()
    vectorbt_ok = test_vectorbt_import()
    
    if numba_ok and vectorbt_ok:
        print("\n✅ Todo configurado correctamente")
        sys.exit(0)
    else:
        print("\n❌ Hay problemas con las importaciones")
        sys.exit(1)
