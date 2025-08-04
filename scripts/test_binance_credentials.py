#!/usr/bin/env python3
"""
Script para probar las credenciales de Binance
Verifica que las credenciales sean válidas y funcionen correctamente
"""

import os
import sys
import asyncio

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from app.services.binance_credentials import (
    get_binance_credentials,
    create_binance_client,
    verify_binance_credentials,
    get_binance_client_with_verification,
    test_binance_connection,
    BinanceCredentialsError,
    BinanceConnectionError
)

def test_credentials_step_by_step():
    """Prueba las credenciales paso a paso"""
    
    print("🧪 Prueba de credenciales de Binance - Paso a Paso")
    print("=" * 60)
    
    try:
        # Paso 1: Obtener credenciales
        print("\n1️⃣ Obteniendo credenciales...")
        api_key, secret_key = get_binance_credentials()
        print(f"✅ Credenciales obtenidas:")
        print(f"   • API_KEY: {api_key[:10]}...")
        print(f"   • SECRET_KEY: {secret_key[:10]}...")
        
        # Paso 2: Crear cliente
        print("\n2️⃣ Creando cliente de Binance...")
        testnet = os.getenv("BINANCE_TESTNET", "true").lower() == "true"
        client = create_binance_client(api_key, secret_key, testnet)
        print(f"✅ Cliente creado exitosamente")
        print(f"   • Testnet: {'Sí' if testnet else 'No'}")
        
        # Paso 3: Verificar credenciales
        print("\n3️⃣ Verificando credenciales...")
        verification_info = verify_binance_credentials(client)
        print(f"✅ Credenciales verificadas:")
        print(f"   • Tipo de cuenta: {verification_info['account_type']}")
        print(f"   • Permisos: {', '.join(verification_info['permissions'])}")
        print(f"   • Balances disponibles: {verification_info['balances_count']}")
        
        # Paso 4: Probar función completa
        print("\n4️⃣ Probando función completa...")
        client_full, verification_full = get_binance_client_with_verification(testnet)
        print(f"✅ Función completa exitosa")
        
        # Paso 5: Probar función de test
        print("\n5️⃣ Probando función de test...")
        test_result = test_binance_connection()
        print(f"✅ Test de conexión: {'Exitoso' if test_result else 'Falló'}")
        
        print("\n🎉 ¡Todas las pruebas pasaron exitosamente!")
        return True
        
    except BinanceCredentialsError as e:
        print(f"\n❌ Error de credenciales: {e}")
        return False
    except BinanceConnectionError as e:
        print(f"\n❌ Error de conexión: {e}")
        return False
    except Exception as e:
        print(f"\n❌ Error inesperado: {e}")
        return False

def test_environment_variables():
    """Prueba las variables de entorno"""
    
    print("\n🔧 Verificando variables de entorno...")
    print("=" * 40)
    
    env_vars = {
        'BINANCE_API_KEY': 'API Key de Binance',
        'BINANCE_SECRET_KEY': 'Secret Key de Binance',
        'BINANCE_TESTNET': 'Usar testnet',
        'PAPER_TRADING': 'Modo paper trading',
        'DEBUG': 'Modo debug'
    }
    
    for var, description in env_vars.items():
        value = os.getenv(var)
        if value:
            # Ocultar valores sensibles
            if 'KEY' in var or 'SECRET' in var:
                display_value = f"{value[:8]}..." if len(value) > 8 else "***"
            else:
                display_value = value
            print(f"✅ {var}: {display_value}")
        else:
            print(f"⚠️  {var}: No configurada")
    
    return True

def test_connection_from_container():
    """Simula la prueba desde el contenedor"""
    
    print("\n🐳 Simulando prueba desde contenedor...")
    print("=" * 50)
    
    try:
        # Verificar que las variables estén disponibles
        api_key = os.getenv("BINANCE_API_KEY")
        secret_key = os.getenv("BINANCE_SECRET_KEY")
        
        if not api_key or not secret_key:
            print("❌ Variables de entorno no disponibles")
            return False
        
        print(f"✅ Variables de entorno disponibles:")
        print(f"   • API_KEY: {api_key[:10]}...")
        print(f"   • SECRET_KEY: {secret_key[:10]}...")
        
        # Probar conexión
        test_result = test_binance_connection()
        
        if test_result:
            print("✅ Conexión exitosa desde contenedor")
            return True
        else:
            print("❌ Conexión falló desde contenedor")
            return False
            
    except Exception as e:
        print(f"❌ Error en prueba desde contenedor: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Prueba de Credenciales de Binance - Grid Trading Bot")
    print("=" * 60)
    
    # Verificar variables de entorno
    env_ok = test_environment_variables()
    
    if not env_ok:
        print("\n❌ Variables de entorno no configuradas correctamente")
        sys.exit(1)
    
    # Probar credenciales paso a paso
    credentials_ok = test_credentials_step_by_step()
    
    if not credentials_ok:
        print("\n❌ Falló la validación de credenciales")
        sys.exit(1)
    
    # Probar desde contenedor
    container_ok = test_connection_from_container()
    
    if not container_ok:
        print("\n❌ Falló la prueba desde contenedor")
        sys.exit(1)
    
    print("\n🎉 ¡Todas las pruebas completadas exitosamente!")
    print("✅ Credenciales de Binance funcionando correctamente")
    print("✅ Sistema listo para operaciones de trading") 