"""
ReconciliationService: Reconcilia estado interno vs Binance y emite métricas.
"""

from __future__ import annotations

import asyncio
import time
from typing import Dict, Any
from app.services.binance_client_singleton import get_binance_client_singleton
from app.core.metrics import portfolio_total_value_usdt, cash_balance_usdt

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
            # Datos de Binance (usar total: free+locked) y valorizar portafolio
            acct = self._client.get_account()
            ext_balances = {}
            for b in acct.get('balances', []):
                asset = b.get('asset')
                free = float(b.get('free', 0) or 0)
                locked = float(b.get('locked', 0) or 0)
                total = free + locked
                if total > 0:
                    ext_balances[asset] = total
            ext_usdt = ext_balances.get('USDT', 0.0)

            # Valorización total del portafolio en USDT
            total_value = float(ext_usdt)
            client_singleton = get_binance_client_singleton()
            for asset, qty in ext_balances.items():
                if asset == 'USDT':
                    continue
                price = client_singleton.get_symbol_price(f"{asset}USDT")
                if price and price > 0:
                    total_value += qty * price
            # Exportar métrica
            try:
                portfolio_total_value_usdt.labels(strategy="grid").set(total_value)
                cash_balance_usdt.labels(strategy="grid").set(ext_usdt)
            except Exception:
                pass

            # Datos internos (placeholder: usar 0 hasta integrar DB)
            int_usdt = 0.0

            has_internal_accounting = int_usdt > 0.0
            if has_internal_accounting:
                discrepancy = abs(ext_usdt - int_usdt)
            else:
                discrepancy = 0.0
            balance_discrepancy_usd.set(discrepancy)
            unaccounted_pnl_usd.set(0.0)

            # Activar breaker si supera umbral relativo (contra max(1.0, ext_usdt))
            # Evitar activar cuando int_usdt es placeholder (0.0) y no existe contabilidad interna
            denom = max(1.0, ext_usdt)
            relative_gap = (discrepancy / denom) if denom > 0 else 0.0
            if has_internal_accounting and relative_gap > self._threshold_pct:
                await self._breakers.activate_breaker('system_integrity', 'balance_discrepancy')

            elapsed = time.time() - start
            reconciliation_latency_seconds.observe(elapsed)
            return {
                'status': 'ok',
                'ext_usdt': ext_usdt,
                'portfolio_total_usdt': round(total_value, 2),
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


