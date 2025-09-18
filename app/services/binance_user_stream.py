from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, Callable

import aiohttp


class BinanceUserStream:
    """
    Mínimo consumidor de userDataStream.
    - Crea listenKey
    - Conecta a wss /stream?streams=<listenKey>
    - Emite callbacks ante executionReport (fills/cancels)
    """

    def __init__(self, api_key: str, session: aiohttp.ClientSession | None = None) -> None:
        self._api_key = api_key
        self._session = session or aiohttp.ClientSession()
        self._listen_key: str | None = None
        self._running = False
        self._on_event: Callable[[Dict[str, Any]], None] | None = None

    async def _create_listen_key(self) -> str:
        async with self._session.post(
            "https://api.binance.com/api/v3/userDataStream",
            headers={"X-MBX-APIKEY": self._api_key},
        ) as resp:
            data = await resp.json()
            return data.get("listenKey")

    async def start(self, on_event: Callable[[Dict[str, Any]], None]) -> None:
        self._on_event = on_event
        self._listen_key = await self._create_listen_key()
        ws_url = f"wss://stream.binance.com:9443/stream?streams={self._listen_key}"
        self._running = True
        async with self._session.ws_connect(ws_url) as ws:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = msg.json()
                    payload = data.get("data") or {}
                    if payload.get("e") == "executionReport" and self._on_event:
                        try:
                            self._on_event(payload)
                        except Exception:
                            pass
                if not self._running:
                    break

    async def stop(self) -> None:
        self._running = False
        try:
            await self._session.close()
        except Exception:
            pass
