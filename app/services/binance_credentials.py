"""
Stub liviano para facilitar tests que hacen patch de get_binance_client_with_verification.
"""
from typing import Tuple, Dict, Any

class _FakeClient:
    api_key: str = "test"
    api_secret: str = "test"

def get_binance_client_with_verification() -> Tuple[_FakeClient, Dict[str, Any]]:
    client = _FakeClient()
    return client, {"valid": True, "account_info": {"balances": []}, "account_type": "SPOT"}

# Backwards-compatible export path expected by tests
get_binance_client_with_verification = get_binance_client_with_verification

#!/usr/bin/env python3
"""
Módulo para manejo robusto de credenciales de Binance
Incluye validación, verificación y manejo de errores
"""

import os
import logging
from typing import Optional, Tuple, Dict, Any
from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceRequestException
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
load_dotenv()

logger = logging.getLogger(__name__)

class BinanceCredentialsError(Exception):
    """Excepción personalizada para errores de credenciales de Binance"""
    pass

class BinanceConnectionError(Exception):
    """Excepción personalizada para errores de conexión con Binance"""
    pass

def get_binance_credentials() -> Tuple[Optional[str], Optional[str]]:
    """
    Obtiene y valida las credenciales de Binance desde variables de entorno
    
    Returns:
        Tuple[Optional[str], Optional[str]]: (api_key, secret_key)
        
    Raises:
        BinanceCredentialsError: Si las credenciales no están disponibles o son inválidas
    """
    api_key = os.getenv("BINANCE_API_KEY")
    secret_key = os.getenv("BINANCE_SECRET_KEY")
    
    # Validación básica de presencia
    if not api_key or not secret_key:
        logger.error("❌ Faltan credenciales de Binance en las variables de entorno")
        logger.error(f"   API_KEY presente: {bool(api_key)}")
        logger.error(f"   SECRET_KEY presente: {bool(secret_key)}")
        raise BinanceCredentialsError("Faltan credenciales de Binance")
    
    # Validación de formato (no vacías, sin espacios en blanco)
    api_key = api_key.strip()
    secret_key = secret_key.strip()
    
    if not api_key or not secret_key:
        logger.error("❌ Credenciales de Binance están vacías o contienen solo espacios")
        raise BinanceCredentialsError("Credenciales de Binance vacías")
    
    # Log en modo DEBUG
    debug_mode = os.getenv("DEBUG", "false").lower() == "true"
    if debug_mode:
        logger.debug(f"🔍 API_KEY: {api_key[:6]}...")
        logger.debug(f"🔍 SECRET_KEY: {secret_key[:6]}...")
    else:
        logger.info(f"✅ API_KEY: {api_key[:10]}...")
        logger.info(f"✅ SECRET_KEY: {secret_key[:10]}...")
    
    return api_key, secret_key

def create_binance_client(api_key: str, secret_key: str, testnet: bool = True) -> Client:
    """
    Crea un cliente de Binance con validación robusta
    
    Args:
        api_key: API key de Binance
        secret_key: Secret key de Binance
        testnet: Si usar testnet (default: True)
        
    Returns:
        Client: Cliente de Binance configurado
        
    Raises:
        BinanceCredentialsError: Si las credenciales son inválidas
        BinanceConnectionError: Si no se puede conectar a Binance
    """
    try:
        # Validar credenciales antes de crear el cliente
        if not api_key or not secret_key:
            raise BinanceCredentialsError("Credenciales vacías")
        
        logger.info(f"🔧 Creando cliente Binance - API Key: {api_key[:10]}..., Testnet: {testnet}")
        
        # Crear cliente
        if testnet:
            client = Client(api_key, secret_key, testnet=True)
            logger.info("🔗 Cliente de Binance Testnet creado")
        else:
            client = Client(api_key, secret_key)
            logger.info("🔗 Cliente de Binance Mainnet creado")
        
        # Verificar que el cliente tenga las credenciales asignadas
        if hasattr(client, 'api_key') and client.api_key:
            logger.info(f"✅ Cliente creado con API key: {client.api_key[:10]}...")
        else:
            logger.error("❌ Cliente creado pero sin API key asignada")
            # Intentar asignar manualmente
            client.api_key = api_key
            client.api_secret = secret_key
            logger.info("🔧 API key asignada manualmente")
        
        return client
        
    except Exception as e:
        logger.error(f"❌ Error creando cliente de Binance: {e}")
        raise BinanceConnectionError(f"No se pudo crear cliente de Binance: {e}")

def verify_binance_credentials(client: Client) -> Dict[str, Any]:
    """
    Verifica que las credenciales de Binance sean válidas y funcionen
    
    Args:
        client: Cliente de Binance ya creado
        
    Returns:
        Dict[str, Any]: Información de la cuenta si las credenciales son válidas
        
    Raises:
        BinanceCredentialsError: Si las credenciales son inválidas
        BinanceConnectionError: Si hay problemas de conexión
    """
    try:
        logger.info("🔍 Verificando credenciales de Binance...")
        
        # Intentar obtener información de la cuenta
        account_info = client.get_account()
        
        # Validar respuesta
        if not account_info:
            raise BinanceCredentialsError("No se pudo obtener información de cuenta")
        
        # Extraer información relevante
        account_type = account_info.get('accountType', 'N/A')
        permissions = account_info.get('permissions', [])
        balances_count = len(account_info.get('balances', []))
        
        logger.info(f"✅ Credenciales verificadas exitosamente")
        logger.info(f"   • Tipo de cuenta: {account_type}")
        logger.info(f"   • Permisos: {', '.join(permissions)}")
        logger.info(f"   • Balances disponibles: {balances_count}")
        
        return {
            "valid": True,
            "account_type": account_type,
            "permissions": permissions,
            "balances_count": balances_count,
            "account_info": account_info
        }
        
    except BinanceAPIException as e:
        if e.code == -2015:
            logger.error("❌ API Secret required for private endpoints")
            logger.error("   Verifica que las credenciales sean correctas")
            raise BinanceCredentialsError("Credenciales inválidas - API Secret required")
        elif e.code == -2013:
            logger.error("❌ Invalid API-key")
            raise BinanceCredentialsError("API Key inválida")
        else:
            logger.error(f"❌ Error de API de Binance: {e}")
            raise BinanceCredentialsError(f"Error de API: {e}")
            
    except BinanceRequestException as e:
        logger.error(f"❌ Error de conexión con Binance: {e}")
        raise BinanceConnectionError(f"Error de conexión: {e}")
        
    except Exception as e:
        logger.error(f"❌ Error inesperado verificando credenciales: {e}")
        raise BinanceConnectionError(f"Error inesperado: {e}")

def get_binance_client_with_verification(testnet: bool = True) -> Tuple[Client, Dict[str, Any]]:
    """
    Función principal que obtiene credenciales, crea cliente y verifica conexión
    
    Args:
        testnet: Si usar testnet (default: True)
        
    Returns:
        Tuple[Client, Dict[str, Any]]: (cliente, información_de_verificación)
        
    Raises:
        BinanceCredentialsError: Si las credenciales son inválidas
        BinanceConnectionError: Si hay problemas de conexión
    """
    try:
        # 1. Obtener y validar credenciales
        api_key, secret_key = get_binance_credentials()
        
        # 2. Crear cliente
        client = create_binance_client(api_key, secret_key, testnet)
        
        # Verificar que el cliente tenga las credenciales
        if not hasattr(client, 'api_key') or not client.api_key:
            logger.error("❌ Cliente creado pero sin API key")
            raise BinanceCredentialsError("Cliente sin API key")
        
        logger.info(f"✅ Cliente creado con API key: {client.api_key[:10]}...")
        
        # 3. Verificar credenciales
        verification_info = verify_binance_credentials(client)
        
        logger.info("🎉 Cliente de Binance configurado y verificado exitosamente")
        return client, verification_info
        
    except (BinanceCredentialsError, BinanceConnectionError):
        # Re-lanzar excepciones específicas
        raise
    except Exception as e:
        logger.error(f"❌ Error inesperado configurando cliente de Binance: {e}")
        raise BinanceConnectionError(f"Error inesperado: {e}")

def test_binance_connection() -> bool:
    """
    Función de prueba para verificar conexión con Binance
    
    Returns:
        bool: True si la conexión es exitosa, False en caso contrario
    """
    try:
        # Obtener configuración de testnet desde variables de entorno
        testnet = os.getenv("BINANCE_TESTNET", "true").lower() == "true"
        
        client, verification_info = get_binance_client_with_verification(testnet)
        logger.info("✅ Prueba de conexión con Binance exitosa")
        return True
    except Exception as e:
        logger.error(f"❌ Prueba de conexión con Binance falló: {e}")
        return False 