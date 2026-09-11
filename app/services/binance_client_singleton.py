"""
Cliente Binance con patrón Singleton para evitar reinicializaciones innecesarias
"""

import os
import logging
from typing import Optional, Dict
import re
import time
import httpx
from binance.client import Client
from binance.exceptions import BinanceAPIException
import ccxt  # Fallback para validación privada
from dotenv import load_dotenv

from app.core.binance_proxy import get_binance_proxies, get_binance_proxy_url
from app.core.secret_redaction import format_credential_for_log

logger = logging.getLogger(__name__)

_last_ip_alert_ts: float = 0.0
_private_fail_count: int = 0
_circuit_open_until_ts: float = 0.0
_fail_threshold: int = int(os.getenv("BINANCE_PRIVATE_FAIL_THRESHOLD", "3"))
_circuit_open_seconds: int = int(
    os.getenv("BINANCE_PRIVATE_CIRCUIT_OPEN_SECONDS", "300")
)  # 5m


# Stablecoins con valoración ≈ 1 USDT (Earn LD*USDT y spot).
STABLECOIN_ASSETS = frozenset({"USDT", "USDC", "BUSD", "FDUSD", "DAI", "TUSD"})


def binance_earn_underlying_asset(asset: str) -> Optional[str]:
    """
    Binance Simple Earn marca balances como LD{ASSET} (p.ej. LDUSDT, LDETH).

    Retorna el activo subyacente o None si no es un balance Earn.
    No construye pares de trading: LDUSDT no tiene ticker spot válido.
    """
    if not asset:
        return None
    a = asset.upper().replace("-", "").replace("_", "")
    if not a.startswith("LD") or len(a) <= 2:
        return None
    return a[2:] or None


def fallback_ld_prefixed_spot_symbol(sym: str) -> Optional[str]:
    """
    Mapea símbolos sintéticos con prefijo LD (balances earning/staking) a un par spot.

    No concatenar un USDT extra al final: p.ej. LDUSDTBTC debe resolver a USDTBTC,
    no a USDTBTCUSDT. LDUSDTUSDT no tiene par spot válido (core == quote) → None.
    """
    s = sym.upper().replace("-", "").replace("_", "")
    base: Optional[str] = None
    quote: Optional[str] = None
    for q in ("USDT", "BUSD", "BTC", "ETH", "BNB"):
        if s.endswith(q):
            quote = q
            base = s[: -len(q)]
            break
    if not base or not quote:
        return None
    if not base.startswith("LD") or len(base) <= 2:
        return None
    core = base[2:]
    if not core:
        return None
    if core == quote:
        return None
    # Evitar mapear LDUSDT{BTC|ETH|...} → USDT{BTC|...} (ruido Earn mal formado).
    if core in STABLECOIN_ASSETS:
        return None
    return f"{core}{quote}"


def _looks_like_earn_synthetic_symbol(symbol: str) -> bool:
    """True si el ticker parece LD* Earn (con o sin quote concatenado)."""
    s = (symbol or "").upper().replace("-", "").replace("_", "")
    if s.startswith("LD"):
        return True
    for q in ("USDT", "BUSD", "BTC", "ETH", "BNB"):
        if s.endswith(q):
            base = s[: -len(q)]
            if binance_earn_underlying_asset(base) is not None:
                return True
    return False


def _rate_limited_debug_skip_earn(owner: object, symbol: str) -> None:
    _key = f"skip_earn_symbol:{symbol}"
    if not hasattr(owner, "_last_invalid_symbol_ts"):
        owner._last_invalid_symbol_ts = {}
    last_ts = owner._last_invalid_symbol_ts.get(_key, 0.0)
    now_ts = time.time()
    if now_ts - last_ts > 600:
        logger.debug(
            "Omitiendo precio Earn/sintético inválido %s (sin par spot)",
            symbol,
        )
        owner._last_invalid_symbol_ts[_key] = now_ts


def _is_binance_ip_error(exc: BaseException) -> bool:
    """True si Binance rechazó por IP / API-key (−2015, 451, Eligibility)."""
    code = getattr(exc, "code", None)
    error_str = str(exc)
    return (
        code == -2015
        or code == 451
        or "Invalid API-key, IP" in error_str
        or "restricted location" in error_str.lower()
        or "Eligibility" in error_str
    )


def _set_binance_ip_rejected(rejected: bool) -> None:
    """Publica el gauge de estado actual. Nunca debe romper el caller."""
    try:
        from app.core.metrics import binance_ip_rejected

        binance_ip_rejected.set(1 if rejected else 0)
    except Exception:
        pass


def _notify_invalid_ip(reason: str = "Invalid API-key, IP, or permissions") -> None:
    """Notifica por Telegram cuando hay un problema de IP con Binance"""
    global _last_ip_alert_ts
    now = time.time()
    # Cooldown local 30 min (evita martillar ipify); el debounce CEO vive en
    # process_binance_auth_ip_watch (6–12 h).
    if now - _last_ip_alert_ts < 1800:
        return
    _last_ip_alert_ts = now
    public_ip = "desconocida"
    try:
        # Intentar obtener IP desde múltiples fuentes
        for url in [
            "https://api.ipify.org",
            "https://ifconfig.me",
            "https://icanhazip.com",
        ]:
            try:
                resp = httpx.get(url, timeout=3)
                public_ip = resp.text.strip()
                if public_ip:
                    break
            except Exception:
                continue
    except Exception:
        pass

    # Determinar el tipo de error
    is_451_error = (
        "451" in reason
        or "restricted location" in reason.lower()
        or "Eligibility" in reason
    )
    error_type = (
        "451 (Ubicación restringida)" if is_451_error else "-2015 (IP no autorizada)"
    )

    try:
        from app.core.binance_auth_ip_watch import process_binance_auth_ip_watch
        from app.core.telegram_ceo_copy import ceo_plain_enabled, render_invalid_ip_telegram
        from app.services.telegram_alert import send_telegram_alert

        if ceo_plain_enabled():
            msg = process_binance_auth_ip_watch(
                blocked=True,
                public_ip=public_ip,
                location_restricted=is_451_error,
            )
            if msg:
                send_telegram_alert(msg)
        else:
            msg = (
                f"⚠️ Binance {error_type}\n\n"
                f"📋 Motivo: {reason}\n"
                f"🌐 IP pública actual: {public_ip}\n\n"
                f"🔧 Acción requerida:\n"
            )
            if is_451_error:
                msg += (
                    "• Binance bloquea conexiones desde esta región del servidor\n"
                    "• Opciones:\n"
                    "  1. Usar un servidor/VPS en región permitida\n"
                    "  2. Configurar Fixie addon en Heroku para IP estática\n"
                    "  3. Contactar a Binance para verificar elegibilidad\n"
                    f"• IP actual: {public_ip}\n"
                )
            else:
                msg += (
                    f"• Agrega la IP {public_ip} en la whitelist de Binance\n"
                    "• O desactiva la restricción de IP en la configuración de la API Key\n"
                )
            msg += "\n📡 Endpoint para consultar IP: /ip"
            send_telegram_alert(msg)
    except Exception as e:
        logger.warning(f"No se pudo enviar alerta Telegram: {e}")
    # Registrar métrica si es posible
    try:
        from app.core.metrics import external_auth_failures

        reason_label = "restricted_location" if is_451_error else "invalid_ip"
        external_auth_failures.labels(provider="binance", reason=reason_label).inc()
    except Exception:
        pass


def _public_binance_ping_ok() -> bool:
    """Ping público corto. Fallback si ``Client.ping()`` está stale (sesión Celery)."""
    try:
        testnet = os.getenv("BINANCE_TESTNET", "false").lower() == "true"
        url = (
            "https://testnet.binance.vision/api/v3/ping"
            if testnet
            else "https://api.binance.com/api/v3/ping"
        )
        kwargs: Dict = {"timeout": 4.0}
        proxy = get_binance_proxy_url()
        if proxy:
            kwargs["proxy"] = proxy
        r = httpx.get(url, **kwargs)
        return int(getattr(r, "status_code", 0) or 0) == 200
    except TypeError:
        try:
            r = httpx.get(url, timeout=4.0)
            return int(getattr(r, "status_code", 0) or 0) == 200
        except Exception:
            return False
    except Exception:
        return False


class BinanceClientSingleton:
    """
    Cliente Binance con patrón Singleton para evitar reinicializaciones
    """

    _instance: Optional["BinanceClientSingleton"] = None
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

            logger.info(
                "🔧 Inicializando cliente Binance Singleton - "
                f"{format_credential_for_log(api_key, label='api_key')}, Testnet: {testnet}"
            )
            from app.core.binance_proxy import log_proxy_status

            log_proxy_status()
            proxies = get_binance_proxies()
            request_kw: Dict = {}
            if proxies:
                request_kw["requests_params"] = {"proxies": proxies}
            # Crear cliente
            if testnet:
                self._client = Client(api_key, api_secret, testnet=True, **request_kw)
                logger.info("🔗 Cliente de Binance Testnet creado")
            else:
                self._client = Client(api_key, api_secret, **request_kw)
                logger.info("🔗 Cliente de Binance Mainnet creado")

            # Asignar credenciales explícitamente
            self._client.api_key = api_key
            self._client.api_secret = api_secret

            # Verificar credenciales
            if hasattr(self._client, "api_key") and self._client.api_key:
                logger.info(
                    "✅ Cliente Singleton creado con "
                    f"{format_credential_for_log(self._client.api_key, label='api_key')}"
                )
            else:
                raise ValueError("No se pudieron asignar las credenciales al cliente")

            # Verificar conexión (privado) y fallback a ping público si falla
            try:
                account_info = self._client.get_account()
                _set_binance_ip_rejected(False)
                logger.info(
                    f"✅ Conexión verificada - Balances disponibles: {len(account_info['balances'])}"
                )
            except BinanceAPIException as auth_err:
                auth_err_str = str(auth_err)
                is_ip_error = _is_binance_ip_error(auth_err)
                if is_ip_error:
                    _set_binance_ip_rejected(True)
                    _notify_invalid_ip(auth_err_str)
                try:
                    from app.core.metrics import binance_api_errors_total

                    binance_api_errors_total.labels(
                        code=str(getattr(auth_err, "code", "unknown")), phase="init"
                    ).inc()
                except Exception:
                    pass
                # Intentar un ping público para aislar credenciales vs conectividad
                try:
                    _ = self._client.ping()
                    logger.error(
                        f"❌ get_account() falló: {auth_err}. Intentando fallback ccxt para validar credenciales…"
                    )
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
        # Check público (sesión python-binance puede estar stale en Celery)
        try:
            session = getattr(client, "session", None)
            if session is not None and getattr(session, "timeout", None) in (None, 0):
                try:
                    session.timeout = 4
                except Exception:
                    pass
            client.ping()
            result["net_ok"] = True
        except Exception as ping_exc:
            result["net_ok"] = _public_binance_ping_ok()
            if result["net_ok"]:
                logger.warning(
                    "Client.ping() falló (%s); ping público /api/v3/ping OK",
                    ping_exc,
                )
            else:
                logger.warning("Binance net check failed: %s", ping_exc)
        # Check privado
        ip_rejected = False
        try:
            client.get_account()
            result["auth_ok"] = True
        except BinanceAPIException as e:
            error_str = str(e)
            is_ip_error = _is_binance_ip_error(e)
            if is_ip_error:
                ip_rejected = True
                _notify_invalid_ip(error_str)
            try:
                from app.core.metrics import binance_api_errors_total

                binance_api_errors_total.labels(
                    code=str(getattr(e, "code", "unknown")), phase="validate"
                ).inc()
            except Exception:
                pass
            # Fallback ccxt
            try:
                api_key = os.getenv("BINANCE_API_KEY")
                api_secret = os.getenv("BINANCE_SECRET_KEY")
                ex = ccxt.binance(
                    {"apiKey": api_key, "secret": api_secret, "enableRateLimit": True}
                )
                _bal = ex.fetch_balance()
                result["auth_ok"] = True
            except Exception:
                result["auth_ok"] = False
        except Exception:
            # Fallback ccxt
            try:
                api_key = os.getenv("BINANCE_API_KEY")
                api_secret = os.getenv("BINANCE_SECRET_KEY")
                ex = ccxt.binance(
                    {"apiKey": api_key, "secret": api_secret, "enableRateLimit": True}
                )
                _bal = ex.fetch_balance()
                result["auth_ok"] = True
            except Exception:
                result["auth_ok"] = False
        result["ok"] = result["net_ok"] and result["auth_ok"]
        if ip_rejected:
            result["auth_ok"] = False
            result["ok"] = False
            _set_binance_ip_rejected(True)
        elif result["auth_ok"]:
            _set_binance_ip_rejected(False)
            try:
                from app.core.binance_auth_ip_watch import process_binance_auth_ip_watch
                from app.services.telegram_alert import send_telegram_alert

                recovered = process_binance_auth_ip_watch(
                    blocked=False,
                    python_binance_auth_ok=True,
                )
                if recovered:
                    send_telegram_alert(recovered)
            except Exception:
                pass
        return result

    def get_account_info(self):
        """Obtiene información de la cuenta (retorna dict vacío si no listo)."""
        client = self.client
        if client is None:
            logger.warning(
                "Cliente Binance no inicializado - get_account_info() retorna {}"
            )
            return {"balances": []}
        try:
            # Circuit open: saltar llamadas privadas por ventana definida
            global _private_fail_count, _circuit_open_until_ts
            if time.time() < _circuit_open_until_ts:
                logger.warning(
                    "Circuito privado abierto para Binance: omitiendo get_account_info"
                )
                return {"balances": []}
            account = client.get_account()
            _set_binance_ip_rejected(False)
            try:
                from app.core.binance_auth_ip_watch import process_binance_auth_ip_watch

                process_binance_auth_ip_watch(
                    blocked=False, python_binance_auth_ok=True
                )
            except Exception:
                pass
            return account
        except BinanceAPIException as e:
            # Declaración global ya realizada arriba de este bloque
            _private_fail_count += 1
            e_str = str(e)
            is_ip_error = _is_binance_ip_error(e)
            if is_ip_error:
                _set_binance_ip_rejected(True)
                _notify_invalid_ip(e_str)
            if _private_fail_count >= _fail_threshold:
                _circuit_open_until_ts = time.time() + _circuit_open_seconds
                logger.warning(
                    f"Circuito privado abierto { _circuit_open_seconds }s por fallos consecutivos ({_private_fail_count})"
                )
                _private_fail_count = 0
            try:
                from app.core.metrics import binance_api_errors_total

                binance_api_errors_total.labels(
                    code=str(getattr(e, "code", "unknown")), phase="get_account"
                ).inc()
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

        for balance in account["balances"]:
            asset = balance["asset"]
            free = float(balance["free"])
            locked = float(balance["locked"])
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

        client = self.client
        if client is None:
            logger.warning(
                "Cliente Binance no inicializado - get_symbol_price() retorna 0.0"
            )
            return 0.0
        try:
            # Normalización y cache
            symbol = _normalize_symbol(symbol)
            cached = _cache.get(symbol)
            if cached:
                symbol = cached
            ticker = client.get_symbol_ticker(symbol=symbol)
            return float(ticker["price"])
        except BinanceAPIException as e:
            if getattr(e, "code", None) == -1121:  # Invalid symbol
                fb = fallback_ld_prefixed_spot_symbol(symbol)
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
                            logger.info(
                                f"Símbolo inválido {symbol}, usando fallback {fb}"
                            )
                            self._last_invalid_symbol_ts[_key] = now_ts
                            try:
                                from app.core.metrics import invalid_symbol_total

                                invalid_symbol_total.labels(symbol=symbol).inc()
                            except Exception:
                                pass
                        return float(ticker["price"])
                    except Exception as inner:
                        logger.error(
                            f"Fallback de símbolo fallido {symbol}->{fb}: {inner}"
                        )
                        return 0.0
                if _looks_like_earn_synthetic_symbol(symbol):
                    _rate_limited_debug_skip_earn(self, symbol)
                    return 0.0
            logger.error(f"Error obteniendo precio para {symbol}: {e}")
            return 0.0
        except Exception as e:
            # Compatibilidad con clientes que lanzan otras clases de excepción
            if "Invalid symbol" in str(e):
                fb = fallback_ld_prefixed_spot_symbol(symbol)
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
                            logger.info(
                                f"Símbolo inválido {symbol}, usando fallback {fb}"
                            )
                            self._last_invalid_symbol_ts[_key] = now_ts
                            try:
                                from app.core.metrics import invalid_symbol_total

                                invalid_symbol_total.labels(symbol=symbol).inc()
                            except Exception:
                                pass
                        return float(ticker["price"])
                    except Exception as inner:
                        logger.error(
                            f"Fallback de símbolo fallido {symbol}->{fb}: {inner}"
                        )
                        return 0.0
                if _looks_like_earn_synthetic_symbol(symbol):
                    _rate_limited_debug_skip_earn(self, symbol)
                    return 0.0
            logger.error(f"Error obteniendo precio para {symbol}: {e}")
            return 0.0

    def create_order(
        self, symbol: str, side: str, order_type: str, quantity: str, **kwargs
    ):
        """Crea una orden en Binance (solo si effective_mode=real_armed)."""
        from app.core.order_execution_guard import assert_real_order_allowed

        assert_real_order_allowed(context="BinanceClientSingleton.create_order")
        return self.client.create_order(
            symbol=symbol, side=side, type=order_type, quantity=quantity, **kwargs
        )

    def get_symbol_info(self, symbol: str):
        """Obtiene información de un símbolo"""
        return self.client.get_symbol_info(symbol)

    def get_exchange_info(self, use_cache: bool = True):
        """
        Obtiene información del exchange con cache opcional (TTL 1 hora)

        ✅ FIX: Cache implementado para reducir llamadas a API
        exchange_info cambia raramente, cache por 1 hora es seguro

        Args:
            use_cache: Si True, usa cache Redis (TTL 1 hora)

        Returns:
            Dict con información del exchange
        """
        # Cache en memoria simple (fallback si Redis no está disponible)
        if not hasattr(self, "_exchange_info_cache"):
            self._exchange_info_cache = {}
            self._exchange_info_cache_ts = 0

        cache_ttl = 3600  # 1 hora

        # Verificar cache en memoria primero
        if use_cache and time.time() - self._exchange_info_cache_ts < cache_ttl:
            if "exchange_info" in self._exchange_info_cache:
                logger.debug("📦 Exchange info obtenido desde cache en memoria")
                return self._exchange_info_cache["exchange_info"]

        # Intentar obtener desde Redis cache
        if use_cache:
            try:
                import asyncio
                from app.core.redis_cache import redis_cache

                # Intentar obtener desde cache Redis (sync wrapper)
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # Si hay loop corriendo, necesitamos ejecutar async en thread
                        import concurrent.futures

                        with concurrent.futures.ThreadPoolExecutor() as executor:
                            future = executor.submit(
                                lambda: asyncio.run(redis_cache.get_exchange_info())
                            )
                            cached_info = future.result(timeout=2)
                    else:
                        cached_info = loop.run_until_complete(
                            redis_cache.get_exchange_info()
                        )

                    if cached_info:
                        # Actualizar cache en memoria también
                        self._exchange_info_cache["exchange_info"] = cached_info
                        self._exchange_info_cache_ts = time.time()
                        logger.debug("📦 Exchange info obtenido desde cache Redis")
                        return cached_info
                except RuntimeError:
                    # No hay event loop, crear uno temporal
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        cached_info = loop.run_until_complete(
                            redis_cache.get_exchange_info()
                        )
                        if cached_info:
                            self._exchange_info_cache["exchange_info"] = cached_info
                            self._exchange_info_cache_ts = time.time()
                            logger.debug("📦 Exchange info obtenido desde cache Redis")
                            return cached_info
                    finally:
                        loop.close()
            except Exception as e:
                logger.debug(f"Cache Redis no disponible, obteniendo de Binance: {e}")

        # Obtener de Binance
        try:
            exchange_info = self.client.get_exchange_info()

            # Guardar en cache en memoria
            self._exchange_info_cache["exchange_info"] = exchange_info
            self._exchange_info_cache_ts = time.time()

            # Guardar en cache Redis (async, no bloqueante)
            if use_cache:
                try:
                    import asyncio
                    from app.core.redis_cache import redis_cache

                    # Intentar guardar en Redis (no bloquear si falla)
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            # Crear task en background
                            asyncio.create_task(
                                redis_cache.set_exchange_info(exchange_info)
                            )
                        else:
                            loop.run_until_complete(
                                redis_cache.set_exchange_info(exchange_info)
                            )
                    except RuntimeError:
                        # Crear loop temporal
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            loop.run_until_complete(
                                redis_cache.set_exchange_info(exchange_info)
                            )
                        finally:
                            loop.close()
                except Exception as cache_error:
                    logger.debug(f"No se pudo guardar en cache Redis: {cache_error}")

            return exchange_info
        except Exception as e:
            logger.error(f"Error obteniendo exchange_info: {e}")
            raise


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
            binance_client_singleton = BinanceClientSingleton.__new__(
                BinanceClientSingleton
            )
            binance_client_singleton._client = None
            binance_client_singleton._initialized = True
    return binance_client_singleton


# Inicializar la instancia global
try:
    binance_client_singleton = get_binance_client_singleton()
except Exception as e:
    logger.error(f"Error inicializando singleton global: {e}")
    binance_client_singleton = None
