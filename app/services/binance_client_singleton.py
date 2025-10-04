"""
Cliente Binance con patrón Singleton para evitar reinicializaciones innecesarias
"""

import os
import logging
from typing import Optional, Dict
import re
import time
import urllib.request
from binance.client import Client
from binance.exceptions import BinanceAPIException
import ccxt  # Fallback para validación privada
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

_last_ip_alert_ts: float = 0.0
_private_fail_count: int = 0
_circuit_open_until_ts: float = 0.0
_fail_threshold: int = int(os.getenv("BINANCE_PRIVATE_FAIL_THRESHOLD", "3"))
_circuit_open_seconds: int = int(os.getenv("BINANCE_PRIVATE_CIRCUIT_OPEN_SECONDS", "300"))  # 5m

def _notify_invalid_ip(reason: str = "Invalid API-key, IP, or permissions") -> None:
    global _last_ip_alert_ts
    now = time.time()
    # Cooldown 30 minutos
    if now - _last_ip_alert_ts < 1800:
        return
    _last_ip_alert_ts = now
    public_ip = "desconocida"
    try:
        public_ip = urllib.request.urlopen("https://api.ipify.org", timeout=3).read().decode("utf-8")
    except Exception:
        pass
    try:
        from app.services.telegram_alert import send_telegram_alert
        msg = (
            "⚠️ Binance -2015 (IP no autorizada)\n"
            f"Motivo: {reason}\n"
            f"IP pública detectada: {public_ip}\n"
            "Acción: agrega esta IP en la whitelist de Binance o desactiva la restricción en la API Key."
        )
        send_telegram_alert(msg)
    except Exception:
        pass
    # Registrar métrica si es posible
    try:
        from app.core.metrics import external_auth_failures
        external_auth_failures.labels(provider="binance", reason="invalid_ip").inc()
    except Exception:
        pass

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
            # Respetar bandera de entorno BINANCE_TESTNET
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
            
            # Verificar conexión (privado) y fallback a ping público si falla
            try:
                account_info = self._client.get_account()
                logger.info(f"✅ Conexión verificada - Balances disponibles: {len(account_info['balances'])}")
            except BinanceAPIException as auth_err:
                if getattr(auth_err, 'code', None) == -2015 or 'Invalid API-key, IP' in str(auth_err):
                    _notify_invalid_ip(str(auth_err))
                try:
                    from app.core.metrics import binance_api_errors_total
                    binance_api_errors_total.labels(code=str(getattr(auth_err, 'code', 'unknown')), phase='init').inc()
                except Exception:
                    pass
                # Intentar un ping público para aislar credenciales vs conectividad
                try:
                    _ = self._client.ping()
                    logger.error(f"❌ get_account() falló: {auth_err}. Intentando fallback ccxt para validar credenciales…")
                except Exception as net_err:
                    logger.error(f"❌ Error de conectividad con Binance: {net_err}")
                # No derribar cliente aquí; la validación privada usará ccxt como fallback
            except Exception as auth_err:
                try:
                    _ = self._client.ping()
                except Exception:
                    pass
                logger.error(f"❌ Error autenticación Binance: {auth_err}")
            
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

    def is_ready(self) -> bool:
        """Indica si el cliente está listo para endpoints privados."""
        return self._client is not None

    def validate_credentials_and_connectivity(self) -> Dict[str, object]:
        """Valida credenciales (privado) y conectividad (público)."""
        result: Dict[str, object] = {"ok": False, "auth_ok": False, "net_ok": False}
        client = self.client
        if client is None:
            return result
        # Check público
        try:
            client.ping()
            result["net_ok"] = True
        except Exception as _:
            result["net_ok"] = False
        # Check privado
        try:
            client.get_account()
            result["auth_ok"] = True
        except BinanceAPIException as e:
            if getattr(e, 'code', None) == -2015 or 'Invalid API-key, IP' in str(e):
                _notify_invalid_ip(str(e))
            try:
                from app.core.metrics import binance_api_errors_total
                binance_api_errors_total.labels(code=str(getattr(e, 'code', 'unknown')), phase='validate').inc()
            except Exception:
                pass
            # Fallback ccxt
            try:
                api_key = os.getenv("BINANCE_API_KEY")
                api_secret = os.getenv("BINANCE_SECRET_KEY")
                ex = ccxt.binance({"apiKey": api_key, "secret": api_secret, "enableRateLimit": True})
                _bal = ex.fetch_balance()
                result["auth_ok"] = True
            except Exception:
                result["auth_ok"] = False
        except Exception:
            # Fallback ccxt
            try:
                api_key = os.getenv("BINANCE_API_KEY")
                api_secret = os.getenv("BINANCE_SECRET_KEY")
                ex = ccxt.binance({"apiKey": api_key, "secret": api_secret, "enableRateLimit": True})
                _bal = ex.fetch_balance()
                result["auth_ok"] = True
            except Exception:
                result["auth_ok"] = False
        result["ok"] = result["net_ok"] and result["auth_ok"]
        return result
    
    def get_account_info(self):
        """Obtiene información de la cuenta (retorna dict vacío si no listo)."""
        client = self.client
        if client is None:
            logger.warning("Cliente Binance no inicializado - get_account_info() retorna {}")
            return {"balances": []}
        try:
            # Circuit open: saltar llamadas privadas por ventana definida
            global _private_fail_count, _circuit_open_until_ts
            if time.time() < _circuit_open_until_ts:
                logger.warning("Circuito privado abierto para Binance: omitiendo get_account_info")
                return {"balances": []}
            return client.get_account()
        except BinanceAPIException as e:
            # Declaración global ya realizada arriba de este bloque
            _private_fail_count += 1
            if getattr(e, 'code', None) == -2015 or 'Invalid API-key, IP' in str(e):
                _notify_invalid_ip(str(e))
            if _private_fail_count >= _fail_threshold:
                _circuit_open_until_ts = time.time() + _circuit_open_seconds
                logger.warning(f"Circuito privado abierto { _circuit_open_seconds }s por fallos consecutivos ({_private_fail_count})")
                _private_fail_count = 0
            try:
                from app.core.metrics import binance_api_errors_total
                binance_api_errors_total.labels(code=str(getattr(e, 'code', 'unknown')), phase='get_account').inc()
            except Exception:
                pass
            logger.error(f"Error get_account_info: {e}")
            return {"balances": []}
        except Exception as e:
            logger.error(f"Error get_account_info: {e}")
            return {"balances": []}
    
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
        if not symbol:
            logger.error("Símbolo vacío")
            return 0.0
        # Normalización mínima y validación regex
        symbol = symbol.upper()
        if not re.match(r"^[A-Z0-9-_.]{1,20}$", symbol):
            logger.error(f"Símbolo inválido por formato: {symbol}")
            return 0.0
        _norm_cache_key = "_norm_symbol_cache"
        if not hasattr(self, _norm_cache_key):
            setattr(self, _norm_cache_key, {})
        _cache: Dict[str, str] = getattr(self, _norm_cache_key)

        def _normalize_symbol(sym: str) -> str:
            s = sym.upper()
            # Remover separadores comunes
            s = s.replace("-", "").replace("_", "")
            return s

        def _fallback_symbol(sym: str) -> Optional[str]:
            base = sym[:-4] if sym.endswith("USDT") else sym
            # Reglas de normalización simples: tokens con prefijo 'LD' (ej. LDBNB) → base sin 'LD'
            if base.startswith("LD") and len(base) > 2:
                return f"{base[2:]}USDT"
            return None

        client = self.client
        if client is None:
            logger.warning("Cliente Binance no inicializado - get_symbol_price() retorna 0.0")
            return 0.0
        try:
            # Normalización y cache
            symbol = _normalize_symbol(symbol)
            cached = _cache.get(symbol)
            if cached:
                symbol = cached
            ticker = client.get_symbol_ticker(symbol=symbol)
            return float(ticker['price'])
        except BinanceAPIException as e:
            if getattr(e, 'code', None) == -1121:  # Invalid symbol
                fb = _fallback_symbol(symbol)
                if fb and fb != symbol:
                    _cache[symbol] = fb
                    # Limitar logs repetidos por símbolo cada 10 min
                    try:
                        ticker = client.get_symbol_ticker(symbol=fb)
                        _key = f"invalid_symbol:{symbol}"
                        if not hasattr(self, "_last_invalid_symbol_ts"):
                            self._last_invalid_symbol_ts = {}
                        last_ts = self._last_invalid_symbol_ts.get(_key, 0.0)
                        now_ts = time.time()
                        if now_ts - last_ts > 600:
                            logger.info(f"Símbolo inválido {symbol}, usando fallback {fb}")
                            self._last_invalid_symbol_ts[_key] = now_ts
                            try:
                                from app.core.metrics import invalid_symbol_total
                                invalid_symbol_total.labels(symbol=symbol).inc()
                            except Exception:
                                pass
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
                    _cache[symbol] = fb
                    try:
                        ticker = client.get_symbol_ticker(symbol=fb)
                        _key = f"invalid_symbol:{symbol}"
                        if not hasattr(self, "_last_invalid_symbol_ts"):
                            self._last_invalid_symbol_ts = {}
                        last_ts = self._last_invalid_symbol_ts.get(_key, 0.0)
                        now_ts = time.time()
                        if now_ts - last_ts > 600:
                            logger.info(f"Símbolo inválido {symbol}, usando fallback {fb}")
                            self._last_invalid_symbol_ts[_key] = now_ts
                            try:
                                from app.core.metrics import invalid_symbol_total
                                invalid_symbol_total.labels(symbol=symbol).inc()
                            except Exception:
                                pass
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