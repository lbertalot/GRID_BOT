"""
Binance User Data Stream Handler — WebSocket API v3 + Ed25519

Migración desde el endpoint REST deprecado (`/api/v3/userDataStream`, retirado
por Binance el 2026-02-20 → respondía 410 Gone) a la WebSocket API oficial:

    wss://ws-api.binance.com:443/ws-api/v3   (producción)
    wss://ws-api.testnet.binance.vision/ws-api/v3   (testnet)

Flujo:
 1. Abrir WS a `/ws-api/v3`.
 2. Autenticar con `session.logon` firmando con Ed25519.
 3. Suscribir el stream de eventos con `userDataStream.subscribe`.
 4. Procesar eventos (`executionReport`, `outboundAccountPosition`, `balanceUpdate`)
    y ejecutar el callback `on_fill`.

Variables de entorno requeridas:
    BINANCE_ED25519_API_KEY            : API key pública (id de la key Ed25519 en Binance)
    BINANCE_ED25519_PRIVATE_KEY_PATH   : path al PEM con la clave privada Ed25519
    BINANCE_ED25519_PRIVATE_KEY_PEM    : alternativa inline al path (contenido PEM)

Variables opcionales:
    BINANCE_TESTNET=true               : usar testnet
    BINANCE_WS_API_BASE                : override manual del base WS

Mantiene el contrato público previo:
    BinanceUserStreamHandler(api_key=...).start(on_fill=...)
    BinanceUserStreamHandler(...).stop()
    default_on_fill(event)
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import time
import uuid
from typing import Optional, Dict, Any, Callable, Awaitable, Union

import aiohttp
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.core.binance_proxy import get_binance_proxy_url
from app.services.balance_service import BalanceService
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)


OnFill = Callable[[Dict[str, Any]], Union[None, Awaitable[None]]]


class Ed25519Signer:
    """Carga y firma payloads con la clave privada Ed25519."""

    def __init__(self, private_key: Ed25519PrivateKey) -> None:
        self._key = private_key

    @classmethod
    def from_env(cls) -> Optional["Ed25519Signer"]:
        pem_path = os.getenv("BINANCE_ED25519_PRIVATE_KEY_PATH", "").strip()
        pem_inline = os.getenv("BINANCE_ED25519_PRIVATE_KEY_PEM", "").strip()
        passphrase = (
            os.getenv("BINANCE_ED25519_PRIVATE_KEY_PASSPHRASE", "").strip() or None
        )
        pw_bytes = passphrase.encode() if passphrase else None

        pem_bytes: Optional[bytes] = None
        if pem_path:
            try:
                with open(pem_path, "rb") as f:
                    pem_bytes = f.read()
            except Exception as e:
                logger.error(
                    f"❌ No se pudo leer BINANCE_ED25519_PRIVATE_KEY_PATH={pem_path}: {e}"
                )
                return None
        elif pem_inline:
            pem_bytes = pem_inline.encode()

        if not pem_bytes:
            return None

        try:
            key = load_pem_private_key(pem_bytes, password=pw_bytes)
        except Exception as e:
            logger.error(f"❌ Clave privada PEM inválida: {e}")
            return None

        if not isinstance(key, Ed25519PrivateKey):
            logger.error("❌ La clave cargada no es Ed25519")
            return None

        return cls(key)

    def sign(self, payload: str) -> str:
        """Firma el payload (query-string canónico) y devuelve base64."""
        sig = self._key.sign(payload.encode("utf-8"))
        return base64.b64encode(sig).decode("ascii")


class BinanceUserStreamHandler:
    """
    Cliente WS API v3 que mantiene la sesión autenticada (session.logon + Ed25519)
    y la suscripción al user data stream (userDataStream.subscribe).

    El método `start(on_fill=...)` preserva el contrato anterior para no tocar
    `app/main.py` ni el scheduler.
    """

    def __init__(
        self,
        api_base: str = "https://api.binance.com",  # ignorado; mantenido por compat
        ws_base: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> None:
        use_testnet = os.getenv("BINANCE_TESTNET", "false").lower() in {
            "1",
            "true",
            "yes",
        }

        # WS API v3 base (distinto del antiguo stream.binance.com)
        default_ws = (
            "wss://ws-api.testnet.binance.vision/ws-api/v3"
            if use_testnet
            else "wss://ws-api.binance.com:443/ws-api/v3"
        )
        env_override = os.getenv("BINANCE_WS_API_BASE", "").strip()
        self.ws_url: str = env_override or ws_base or default_ws

        # API key pública dedicada al par Ed25519 (NO mezclar con BINANCE_API_KEY HMAC).
        # WS API v3 + session.logon exige que el `apiKey` del payload corresponda
        # exactamente al par Ed25519 registrado en Binance. Si el caller pasa la
        # HMAC legacy, Binance responde -1022 "Signature for this request is not valid".
        #
        # Prioridad:
        #   1. BINANCE_ED25519_API_KEY (la correcta para Ed25519).
        #   2. `api_key` pasado al constructor (solo si no hay Ed25519 en env).
        #   3. BINANCE_API_KEY como último recurso.
        ed25519_env = os.getenv("BINANCE_ED25519_API_KEY", "").strip()
        if ed25519_env:
            self.api_key: str = ed25519_env
            if api_key and api_key.strip() and api_key.strip() != ed25519_env:
                logger.warning(
                    "⚠️ Se pasó api_key al constructor pero se usará "
                    "BINANCE_ED25519_API_KEY del entorno (WS API v3 requiere Ed25519)."
                )
        else:
            self.api_key = (api_key or os.getenv("BINANCE_API_KEY", "")).strip()

        self.signer: Optional[Ed25519Signer] = Ed25519Signer.from_env()
        self._proxy_url: Optional[str] = get_binance_proxy_url()

        self.session: Optional[aiohttp.ClientSession] = None
        self.ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self.running: bool = False
        self.subscription_id: Optional[str] = None

        self._conn_task: Optional[asyncio.Task] = None
        self._reader_task: Optional[asyncio.Task] = None
        self._pending: Dict[str, asyncio.Future] = {}
        self._on_fill: Optional[OnFill] = None

    # ------------------------------------------------------------------ API

    async def start(self, on_fill: OnFill) -> None:
        if self.running:
            return
        if not self.api_key:
            logger.warning(
                "ℹ️ BINANCE_ED25519_API_KEY (o BINANCE_API_KEY) no configurada; "
                "User Data Stream no iniciado"
            )
            return
        if self.signer is None:
            logger.error(
                "❌ Falta clave privada Ed25519 (BINANCE_ED25519_PRIVATE_KEY_PATH "
                "o BINANCE_ED25519_PRIVATE_KEY_PEM). User Data Stream no iniciado."
            )
            return

        self.running = True
        self._on_fill = on_fill
        if self.session is None:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15)
            )
        self._conn_task = asyncio.create_task(self._connection_loop())
        logger.info("✅ BinanceUserStreamHandler iniciado (WS API v3 + Ed25519)")

    async def stop(self) -> None:
        self.running = False
        for t in (self._reader_task, self._conn_task):
            if t and not t.done():
                t.cancel()
        # Cancelar futures pendientes
        for fut in list(self._pending.values()):
            if not fut.done():
                fut.set_exception(RuntimeError("stream shutting down"))
        self._pending.clear()

        if self.ws is not None:
            try:
                await self.ws.close()
            except Exception:
                pass
        if self.session is not None:
            try:
                await self.session.close()
            except Exception:
                pass
        logger.info("🛑 BinanceUserStreamHandler detenido")

    # ------------------------------------------------------------ Internals

    async def _connection_loop(self) -> None:
        backoff = 1
        while self.running:
            try:
                ws_kw: Dict[str, Any] = {"heartbeat": 30}
                if self._proxy_url:
                    ws_kw["proxy"] = self._proxy_url

                logger.info(f"🔗 Conectando a WS API v3: {self.ws_url}")
                assert self.session is not None
                self.ws = await self.session.ws_connect(self.ws_url, **ws_kw)
                logger.info("✅ WS API v3 conectado; iniciando reader + session.logon")

                # Reader debe estar vivo antes de enviar requests que esperan respuesta
                self._reader_task = asyncio.create_task(self._reader_loop())

                await self._session_logon()
                await self._subscribe_user_data()

                backoff = 1
                # Quedamos aquí esperando a que el reader termine (desconexión)
                if self._reader_task:
                    await self._reader_task

            except asyncio.CancelledError:
                break
            except Exception as e:
                try:
                    from app.core.metrics import ws_errors_total, ws_reconnects_total

                    ws_errors_total.labels(phase="connect").inc()
                    ws_reconnects_total.inc()
                except Exception:
                    pass

                err_str = str(e)
                is_auth_error = (
                    "-2015" in err_str
                    or "Invalid API-key" in err_str
                    or "Signature" in err_str
                    or "unauthorized" in err_str.lower()
                )
                if is_auth_error:
                    try:
                        from app.services.binance_client_singleton import (
                            _notify_invalid_ip,
                        )

                        _notify_invalid_ip(err_str)
                    except Exception:
                        pass
                    logger.error(
                        f"❌ Error de autenticación WS API v3: {e!r}. "
                        f"Verifica BINANCE_ED25519_API_KEY, clave privada y whitelist de IP."
                    )
                    await asyncio.sleep(300)  # cooldown largo para errores de auth/IP
                else:
                    logger.error(f"❌ Error en WS API v3: {e!r}")
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 60)

            finally:
                # Limpia estado parcial entre reconexiones
                self.subscription_id = None
                if self.ws is not None:
                    try:
                        await self.ws.close()
                    except Exception:
                        pass
                    self.ws = None
                if self._reader_task and not self._reader_task.done():
                    self._reader_task.cancel()
                self._reader_task = None

    # -------------------------------------------------------------- Signing

    def _canonical_logon_payload(self, timestamp_ms: int) -> str:
        # Orden alfabético de parámetros — Binance exige exactamente este orden.
        return f"apiKey={self.api_key}&timestamp={timestamp_ms}"

    # ------------------------------------------------------ Request/Response

    async def _send_request(
        self,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: float = 10.0,
    ) -> Dict[str, Any]:
        """Envía un request JSON-RPC estilo Binance WS API y espera la respuesta."""
        if self.ws is None:
            raise RuntimeError("WS no conectado")

        req_id = uuid.uuid4().hex
        loop = asyncio.get_event_loop()
        fut: asyncio.Future = loop.create_future()
        self._pending[req_id] = fut

        payload: Dict[str, Any] = {"id": req_id, "method": method}
        if params:
            payload["params"] = params

        await self.ws.send_str(json.dumps(payload))
        try:
            resp = await asyncio.wait_for(fut, timeout=timeout)
        finally:
            self._pending.pop(req_id, None)

        status = resp.get("status")
        if status != 200:
            err = resp.get("error") or {}
            raise RuntimeError(
                f"WS API v3 {method} fallido: status={status} code={err.get('code')} "
                f"msg={err.get('msg')}"
            )
        return resp

    async def _session_logon(self) -> None:
        timestamp = int(time.time() * 1000)
        payload = self._canonical_logon_payload(timestamp)
        assert self.signer is not None
        signature = self.signer.sign(payload)
        params = {
            "apiKey": self.api_key,
            "signature": signature,
            "timestamp": timestamp,
        }
        await self._send_request("session.logon", params=params, timeout=15.0)
        logger.info("🔐 session.logon OK (Ed25519)")

    async def _subscribe_user_data(self) -> None:
        resp = await self._send_request("userDataStream.subscribe", timeout=15.0)
        result = resp.get("result") or {}
        self.subscription_id = str(result.get("subscriptionId") or "")
        logger.info(
            f"📡 userDataStream.subscribe OK (subscriptionId={self.subscription_id})"
        )

    # --------------------------------------------------------------- Reader

    async def _reader_loop(self) -> None:
        assert self.ws is not None
        try:
            async for msg in self.ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                    except Exception as e:
                        logger.error(f"❌ JSON inválido en WS: {e!r}")
                        continue
                    await self._dispatch(data)
                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                    raise RuntimeError(
                        f"WS cerrado o en error (type={msg.type}, data={msg.data!r})"
                    )
        except asyncio.CancelledError:
            raise
        except Exception as e:
            try:
                from app.core.metrics import ws_errors_total

                ws_errors_total.labels(phase="message").inc()
            except Exception:
                pass
            logger.error(f"❌ Reader loop error: {e!r}")
            raise

    async def _dispatch(self, data: Dict[str, Any]) -> None:
        # 1) Respuesta a un request (correlacionada por id)
        if "id" in data and data["id"] in self._pending:
            fut = self._pending.get(data["id"])
            if fut and not fut.done():
                fut.set_result(data)
            return

        # 2) Evento user-data-stream. En WS API v3 puede venir como
        #    {"event": {"e": "executionReport", ...}} o como objeto con "e" en top-level.
        evt = data.get("event") if isinstance(data.get("event"), dict) else data
        etype = evt.get("e")
        if not etype:
            # Mensajes control (p.ej. pong) se ignoran
            logger.debug(f"WS msg sin evento: {data}")
            return

        try:
            from app.core.metrics import ws_events_total

            ws_events_total.labels(event=etype).inc()
        except Exception:
            pass

        if etype == "executionReport":
            await self._invoke_on_fill(evt)
        elif etype in ("outboundAccountPosition", "balanceUpdate", "listenKeyExpired"):
            # Por ahora solo log; el callback original es para fills
            logger.info(f"ℹ️ Evento user-stream: {etype}")
        else:
            logger.debug(f"Evento no manejado: {etype}")

    async def _invoke_on_fill(self, evt: Dict[str, Any]) -> None:
        if self._on_fill is None:
            return
        try:
            from app.core.metrics import ws_fill_latency_seconds

            _start = time.perf_counter()
            result = self._on_fill(evt)
            if asyncio.iscoroutine(result):
                await result
            ws_fill_latency_seconds.observe(time.perf_counter() - _start)
        except Exception as e:
            try:
                from app.core.metrics import ws_errors_total

                ws_errors_total.labels(phase="on_fill").inc()
            except Exception:
                pass
            logger.error(f"❌ Error en callback on_fill: {e!r}")


# --------------------------------------------------------------------------
# Default fill handler (sin cambios funcionales vs. la versión anterior)
# --------------------------------------------------------------------------
async def default_on_fill(event: Dict[str, Any]) -> None:
    """
    Callback por defecto: aplica cambios de balance a partir del executionReport.
    """
    try:
        symbol = event.get("s")
        side = event.get("S")  # BUY/SELL
        status = event.get("X")  # FILLED/PARTIALLY_FILLED/NEW
        executed_qty = event.get("l")  # last executed quantity
        cum_quote = event.get("Z")  # cumulative quote qty

        if status not in ("PARTIALLY_FILLED", "FILLED"):
            return
        if not symbol or not side:
            return

        from decimal import Decimal

        base_asset = symbol[:-4]
        quote_asset = symbol[-4:]

        db = SessionLocal()
        try:
            if side == "BUY":
                if cum_quote:
                    BalanceService.update_balance(
                        db, quote_asset, -Decimal(str(cum_quote))
                    )
                if executed_qty:
                    BalanceService.update_balance(
                        db, base_asset, Decimal(str(executed_qty))
                    )
            else:
                if executed_qty:
                    BalanceService.update_balance(
                        db, base_asset, -Decimal(str(executed_qty))
                    )
                if cum_quote:
                    BalanceService.update_balance(
                        db, quote_asset, Decimal(str(cum_quote))
                    )
        finally:
            try:
                db.close()
            except Exception:
                pass

        logger.info(
            f"⚡ Fill aplicado por WS: {side} {executed_qty} {symbol} (ΣQuote={cum_quote})"
        )
    except Exception as e:
        logger.error(f"❌ Error aplicando fill por WS: {e}")
