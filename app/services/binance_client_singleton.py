"""
Cliente Binance con patrón Singleton para evitar reinicializaciones innecesarias
"""

import os
import logging
from typing import Optional
from binance.client import Client
from binance.exceptions import BinanceAPIException
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

class BinanceClientSingleton:
    """
    Cliente Binance con patrón Singleton para evitar reinicializaciones
    """
    
    _instance: Optional['BinanceClientSingleton'] = None
    _client: Optional[Client] = None
    _initialized: bool = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(BinanceClientSingleton, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self._initialized = True
            self._initialize_client()
    
    def _initialize_client(self):
        """Inicializa el cliente Binance una sola vez"""
        try:
            # Cargar variables de entorno
            load_dotenv()
            
            api_key = os.getenv("BINANCE_API_KEY")
            api_secret = os.getenv("BINANCE_API_SECRET") or os.getenv("BINANCE_SECRET_KEY")
            testnet = os.getenv("BINANCE_TESTNET", "false").lower() == "true"
            
            if not api_key or not api_secret:
                raise ValueError("Credenciales de Binance no configuradas")
            
            logger.info(f"🔧 Inicializando cliente Binance Singleton - API Key: {api_key[:10]}..., Testnet: {testnet}")
            
            # Crear cliente
            if testnet:
                self._client = Client(api_key, api_secret, testnet=True)
                logger.info("🔗 Cliente de Binance Testnet creado")
            else:
                self._client = Client(api_key, api_secret)
                logger.info("🔗 Cliente de Binance Mainnet creado")
            
            # Asignar credenciales explícitamente
            self._client.api_key = api_key
            self._client.api_secret = api_secret
            
            # Verificar credenciales
            if hasattr(self._client, 'api_key') and self._client.api_key:
                logger.info(f"✅ Cliente Singleton creado con API key: {self._client.api_key[:10]}...")
            else:
                raise ValueError("No se pudieron asignar las credenciales al cliente")
            
            # Verificar conexión
            account_info = self._client.get_account()
            logger.info(f"✅ Conexión verificada - Balances disponibles: {len(account_info['balances'])}")
            
        except Exception as e:
            logger.error(f"❌ Error inicializando cliente Singleton: {e}")
            self._client = None
            raise
    
    @property
    def client(self) -> Optional[Client]:
        """Retorna el cliente Binance inicializado"""
        try:
            if self._client is None:
                self._initialize_client()
            return self._client
        except Exception as e:
            logger.error(f"❌ Error obteniendo cliente: {e}")
            return None
    
    def get_account_info(self):
        """Obtiene información de la cuenta"""
        return self.client.get_account()
    
    def get_balances(self):
        """Obtiene balances de la cuenta"""
        account = self.get_account_info()
        balances = {}
        
        for balance in account['balances']:
            asset = balance['asset']
            free = float(balance['free'])
            locked = float(balance['locked'])
            total = free + locked
            
            if total > 0:
                balances[asset] = total
        
        return balances
    
    def get_symbol_price(self, symbol: str) -> float:
        """Obtiene el precio actual de un símbolo"""
        def _fallback_symbol(sym: str) -> Optional[str]:
            base = sym[:-4] if sym.endswith("USDT") else sym
            # Reglas de normalización simples: tokens con prefijo 'LD' (ej. LDBNB) → base sin 'LD'
            if base.startswith("LD") and len(base) > 2:
                return f"{base[2:]}USDT"
            return None

        try:
            ticker = self.client.get_symbol_ticker(symbol=symbol)
            return float(ticker['price'])
        except BinanceAPIException as e:
            if getattr(e, 'code', None) == -1121:  # Invalid symbol
                fb = _fallback_symbol(symbol)
                if fb and fb != symbol:
                    try:
                        ticker = self.client.get_symbol_ticker(symbol=fb)
                        logger.warning(f"Símbolo inválido {symbol}, usando fallback {fb}")
                        return float(ticker['price'])
                    except Exception as inner:
                        logger.error(f"Fallback de símbolo fallido {symbol}->{fb}: {inner}")
                        return 0.0
            logger.error(f"Error obteniendo precio para {symbol}: {e}")
            return 0.0
        except Exception as e:
            # Compatibilidad con clientes que lanzan otras clases de excepción
            if 'Invalid symbol' in str(e):
                fb = _fallback_symbol(symbol)
                if fb and fb != symbol:
                    try:
                        ticker = self.client.get_symbol_ticker(symbol=fb)
                        logger.warning(f"Símbolo inválido {symbol}, usando fallback {fb}")
                        return float(ticker['price'])
                    except Exception as inner:
                        logger.error(f"Fallback de símbolo fallido {symbol}->{fb}: {inner}")
                        return 0.0
            logger.error(f"Error obteniendo precio para {symbol}: {e}")
            return 0.0
    
    def create_order(self, symbol: str, side: str, order_type: str, quantity: str, **kwargs):
        """Crea una orden en Binance"""
        return self.client.create_order(
            symbol=symbol,
            side=side,
            type=order_type,
            quantity=quantity,
            **kwargs
        )
    
    def get_symbol_info(self, symbol: str):
        """Obtiene información de un símbolo"""
        return self.client.get_symbol_info(symbol)

# Instancia global - inicialización lazy
binance_client_singleton = None

def get_binance_client_singleton():
    """Obtiene la instancia singleton del cliente Binance con inicialización lazy"""
    global binance_client_singleton
    if binance_client_singleton is None:
        try:
            binance_client_singleton = BinanceClientSingleton()
        except Exception as e:
            logger.warning(f"No se pudo inicializar el cliente Binance: {e}")
            # Crear una instancia dummy para evitar errores
            binance_client_singleton = BinanceClientSingleton.__new__(BinanceClientSingleton)
            binance_client_singleton._client = None
            binance_client_singleton._initialized = True
    return binance_client_singleton

# Inicializar la instancia global
try:
    binance_client_singleton = get_binance_client_singleton()
except Exception as e:
    logger.error(f"Error inicializando singleton global: {e}")
    binance_client_singleton = None 