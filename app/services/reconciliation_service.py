"""
ReconciliationService: Reconcilia estado interno vs Binance y emite métricas.
"""

from __future__ import annotations

import asyncio
import time
from typing import Dict, Any

from binance.client import Client
from app.core.metrics import (
    reconciliation_latency_seconds,
    balance_discrepancy_usd,
    unaccounted_pnl_usd,
)
from app.core.circuit_breakers import CircuitBreakers


class ReconciliationService:
    def __init__(self, client: Client, breakers: CircuitBreakers, threshold_pct: float = 0.01) -> None:
        self._client = client
        self._breakers = breakers
        self._threshold_pct = threshold_pct
        self._running = False

    async def run_reconciliation_cycle(self) -> Dict[str, Any]:
        start = time.time()
        try:
            # Datos de Binance (simplificado: solo balances libres)
            acct = self._client.get_account()
            ext_balances = {b['asset']: float(b['free']) for b in acct.get('balances', [])}
            ext_usdt = ext_balances.get('USDT', 0.0)

            # Datos internos (placeholder: usar 0 hasta integrar DB)
            int_usdt = 0.0

            discrepancy = abs(ext_usdt - int_usdt)
            balance_discrepancy_usd.set(discrepancy)
            unaccounted_pnl_usd.set(0.0)

            # Activar breaker si supera umbral relativo (contra max(1.0, ext_usdt))
            denom = max(1.0, ext_usdt)
            if (discrepancy / denom) > self._threshold_pct:
                await self._breakers.activate_breaker('system_integrity', 'balance_discrepancy')

            elapsed = time.time() - start
            reconciliation_latency_seconds.observe(elapsed)
            return {
                'status': 'ok',
                'ext_usdt': ext_usdt,
                'int_usdt': int_usdt,
                'discrepancy_usd': discrepancy,
                'latency_seconds': elapsed,
            }
        except Exception as e:
            elapsed = time.time() - start
            reconciliation_latency_seconds.observe(elapsed)
            return {'status': 'error', 'error': str(e), 'latency_seconds': elapsed}

    async def start(self, interval_seconds: int = 60) -> None:
        if self._running:
            return
        self._running = True
        while True:
            try:
                await self.run_reconciliation_cycle()
            except Exception:
                pass
            await asyncio.sleep(interval_seconds)


