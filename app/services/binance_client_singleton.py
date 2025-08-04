"""
Cliente Binance con patrón Singleton para evitar reinicializaciones innecesarias
"""

import os
import logging
from typing import Optional
from binance.client import Client
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
            api_secret = os.getenv("BINANCE_SECRET_KEY")
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
    def client(self) -> Client:
        """Retorna el cliente Binance inicializado"""
        if self._client is None:
            self._initialize_client()
        return self._client
    
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
        try:
            ticker = self.client.get_symbol_ticker(symbol=symbol)
            return float(ticker['price'])
        except Exception as e:
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

# Instancia global
binance_client_singleton = BinanceClientSingleton() 