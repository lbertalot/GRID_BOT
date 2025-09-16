from __future__ import annotations

import asyncio
from typing import Any, Dict

from app.services.binance_client_singleton import get_binance_client_singleton  # type: ignore
from app.services.reconciliation_service import ReconciliationService  # type: ignore
from app.core.circuit_breakers import CircuitBreakers  # type: ignore


async def run_reconciliation_forever(interval_seconds: int = 60) -> None:
    client_singleton = get_binance_client_singleton()
    breakers = CircuitBreakers()
    svc = ReconciliationService(client_singleton.client, breakers)
    while True:
        try:
            await svc.run_reconciliation_cycle()
        except Exception:
            pass
        await asyncio.sleep(interval_seconds)


async def run_reconciliation_once() -> Dict[str, Any]:
    client_singleton = get_binance_client_singleton()
    breakers = CircuitBreakers()
    svc = ReconciliationService(client_singleton.client, breakers)
    return await svc.run_reconciliation_cycle()


