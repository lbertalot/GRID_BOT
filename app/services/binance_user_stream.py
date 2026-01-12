"""
Binance User Data Stream Handler
 - Crea y mantiene listenKey
 - Conecta a WebSocket wss://stream.binance.com:9443/ws/{listenKey}
 - Procesa executionReport (fills) y actualiza balances internos
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Optional, Dict, Any, Callable

import aiohttp

from app.services.balance_service import BalanceService
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)


class BinanceUserStreamHandler:
    def __init__(self, api_base: str = "https://api.binance.com", ws_base: str = "wss://stream.binance.com:9443/ws", api_key: Optional[str] = None):
        # Detectar testnet desde env
        use_testnet = os.getenv("BINANCE_TESTNET", "false").lower() in {"1", "true", "yes"}
        if use_testnet:
            api_base = "https://testnet.binance.vision"
            ws_base = "wss://testnet.binance.vision/ws"
        self.api_base = api_base.rstrip("/")
        self.ws_base = ws_base.rstrip("/")
        self.session: Optional[aiohttp.ClientSession] = None
        self.listen_key: Optional[str] = None
        self.ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self.running: bool = False
        self._keepalive_task: Optional[asyncio.Task] = None
        self._conn_task: Optional[asyncio.Task] = None
        self._on_fill: Optional[Callable[[Dict[str, Any]], None]] = None
        # permitir inyección opcional (fallback a env)
        if api_key:
            os.environ.setdefault("BINANCE_API_KEY", api_key)

    async def start(self, on_fill: Callable[[Dict[str, Any]], None]) -> None:
        if self.running:
            return
        self.running = True
        self._on_fill = on_fill
        if self.session is None:
            self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15))
        self._conn_task = asyncio.create_task(self._connection_loop())
        self._keepalive_task = asyncio.create_task(self._keepalive_loop())
        logger.info("✅ BinanceUserStreamHandler iniciado")

    async def stop(self) -> None:
        self.running = False
        if self._keepalive_task:
            self._keepalive_task.cancel()
        if self._conn_task:
            self._conn_task.cancel()
        if self.ws:
            try:
                await self.ws.close()
            except Exception:
                pass
        if self.session:
            try:
                await self.session.close()
            except Exception:
                pass
        logger.info("🛑 BinanceUserStreamHandler detenido")

    async def _create_listen_key(self) -> str:
        headers = {"X-MBX-APIKEY": os.getenv("BINANCE_API_KEY", "")}
        async with self.session.post(f"{self.api_base}/api/v3/userDataStream", headers=headers) as resp:
            if resp.status != 200:
                text = await resp.text()
                # Manejar específicamente error -2015 (IP no autorizada)
                if resp.status == 401 and ("-2015" in text or "Invalid API-key, IP" in text):
                    error_msg = (
                        f"⚠️ Binance -2015 (IP no autorizada) al crear listenKey. "
                        f"Verifica whitelist de IP en Binance. "
                        f"WebSocket deshabilitado temporalmente."
                    )
                    logger.error(error_msg)
                    # Notificar usando el sistema del singleton
                    try:
                        from app.services.binance_client_singleton import _notify_invalid_ip
                        _notify_invalid_ip("Error creando listenKey: " + text)
                    except Exception:
                        pass
                raise RuntimeError(f"Error creando listenKey: {resp.status} {text}")
            data = await resp.json()
            lk = data.get("listenKey")
            if not lk:
                raise RuntimeError("listenKey no presente en respuesta")
            return lk

    async def _extend_listen_key(self) -> None:
        if not self.listen_key:
            return
        headers = {"X-MBX-APIKEY": os.getenv("BINANCE_API_KEY", "")}
        params = {"listenKey": self.listen_key}
        try:
            async with self.session.put(f"{self.api_base}/api/v3/userDataStream", headers=headers, params=params) as resp:
                if resp.status != 200:
                    logger.warning(f"⚠️ No se pudo extender listenKey: status={resp.status}")
        except Exception as e:
            logger.warning(f"⚠️ Error extendiendo listenKey: {e}")

    async def _keepalive_loop(self) -> None:
        # Extender cada ~25 minutos (Binance exige <60m)
        while self.running:
            try:
                await asyncio.sleep(1500)  # 25 min
                await self._extend_listen_key()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"⚠️ Keepalive error: {e}")

    async def _connection_loop(self) -> None:
        """Loop de conexión con manejo mejorado de errores -2015"""
        backoff = 1
        _last_2015_log_ts = 0.0
        _2015_retry_delay = 300  # 5 minutos entre reintentos para errores -2015
        
        while self.running:
            try:
                self.listen_key = await self._create_listen_key()
                ws_url = f"{self.ws_base}/{self.listen_key}"
                logger.info(f"🔗 Conectando a WS userStream...")
                self.ws = await self.session.ws_connect(ws_url, heartbeat=15)
                logger.info("✅ WS userStream conectado")
                backoff = 1
                _last_2015_log_ts = 0.0  # Resetear si conexión exitosa
                await self._message_loop()
            except asyncio.CancelledError:
                break
            except Exception as e:
                error_str = str(e)
                is_2015_error = "-2015" in error_str or "Invalid API-key, IP" in error_str
                
                # Para errores -2015, usar cooldown más largo y log menos frecuente
                if is_2015_error:
                    now = time.time()
                    if now - _last_2015_log_ts > 300:  # Log cada 5 minutos máximo
                        logger.error(
                            f"❌ Error -2015 en conexión WS (IP no autorizada). "
                            f"Reintentando cada {_2015_retry_delay}s. "
                            f"Verifica whitelist de IP en Binance."
                        )
                        _last_2015_log_ts = now
                    backoff = _2015_retry_delay  # Usar delay más largo para -2015
                else:
                    # Otros errores: log normal y backoff exponencial
                    try:
                        from app.core.metrics import ws_errors_total, ws_reconnects_total
                        ws_errors_total.labels(phase="connect").inc()
                        ws_reconnects_total.inc()
                    except Exception:
                        pass
                    logger.error(f"❌ Error en conexión WS: {e!r}")
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 60)
                    continue
                
                # Para errores -2015, esperar antes de reintentar
                await asyncio.sleep(backoff)

    async def _message_loop(self) -> None:
        assert self.ws is not None
        async for msg in self.ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    await self._handle_event(data)
                except Exception as e:
                    try:
                        from app.core.metrics import ws_errors_total
                        ws_errors_total.labels(phase="message").inc()
                    except Exception:
                        pass
                    logger.error(f"❌ Error procesando mensaje WS: {e!r}")
            elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                raise RuntimeError("WS cerrado o en error")

    async def _handle_event(self, data: Dict[str, Any]) -> None:
        # Binance user data stream: executionReport -> evento de fills
        if data.get("e") == "executionReport":
            try:
                from app.core.metrics import ws_events_total, ws_fill_latency_seconds, ws_errors_total
                import time as _t
                _start = _t.perf_counter()
                if self._on_fill:
                    await self._on_fill(data)
                ws_events_total.labels(event="executionReport").inc()
                ws_fill_latency_seconds.observe(_t.perf_counter() - _start)
            except Exception as e:
                try:
                    from app.core.metrics import ws_errors_total
                    ws_errors_total.labels(phase="on_fill").inc()
                except Exception:
                    pass
                logger.error(f"❌ Error en callback on_fill: {e!r}")


async def default_on_fill(event: Dict[str, Any]) -> None:
    """
    Callback por defecto: aplica cambios de balance a partir del executionReport.
    """
    try:
        # Campos clave
        symbol = event.get("s")
        side = event.get("S")  # BUY/SELL
        status = event.get("X")  # FILLED/PARTIALLY_FILLED/NEW
        executed_qty = event.get("l")  # last executed quantity
        cum_quote = event.get("Z")  # cumulative quote qty

        if status not in ("PARTIALLY_FILLED", "FILLED"):
            return
        if not symbol or not side:
            return

        # Convertir a Decimal-safe strings
        from decimal import Decimal

        base_asset = symbol[:-4]
        quote_asset = symbol[-4:]

        # Usar una sesión de BD por evento
        db = SessionLocal()
        try:
            if side == "BUY":
                # -USDT (Z), +BASE (l)
                if cum_quote:
                    BalanceService.update_balance(db, quote_asset, -Decimal(str(cum_quote)))
                if executed_qty:
                    BalanceService.update_balance(db, base_asset, Decimal(str(executed_qty)))
            else:
                # +USDT (Z), -BASE (l)
                if executed_qty:
                    BalanceService.update_balance(db, base_asset, -Decimal(str(executed_qty)))
                if cum_quote:
                    BalanceService.update_balance(db, quote_asset, Decimal(str(cum_quote)))
        finally:
            try:
                db.close()
            except Exception:
                pass

        logger.info(f"⚡ Fill aplicado por WS: {side} {executed_qty} {symbol} (ΣQuote={cum_quote})")
    except Exception as e:
        logger.error(f"❌ Error aplicando fill por WS: {e}")
