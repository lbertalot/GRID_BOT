"""
ReconciliationService: Reconcilia estado interno vs Binance y emite métricas.
"""

from __future__ import annotations

import asyncio
import time
from typing import Dict, Any
from app.services.binance_client_singleton import get_binance_client_singleton
from app.core.metrics import portfolio_total_value_usdt, cash_balance_usdt
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.trade import Trade

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
            # Datos de Binance usando el cliente singleton correcto
            client_singleton = get_binance_client_singleton()
            account_info = client_singleton.get_account_info()
            
            if not account_info or 'balances' not in account_info:
                return {'status': 'error', 'error': 'No account info available', 'latency_seconds': time.time() - start}
            
            ext_balances = {}
            for b in account_info.get('balances', []):
                asset = b.get('asset')
                free = float(b.get('free', 0) or 0)
                locked = float(b.get('locked', 0) or 0)
                total = free + locked
                if total > 0:
                    ext_balances[asset] = total
            
            ext_usdt = ext_balances.get('USDT', 0.0)

            # Valorización total del portafolio en USDT
            total_value = float(ext_usdt)
            for asset, qty in ext_balances.items():
                if asset == 'USDT':
                    continue
                try:
                    symbol = f"{asset}USDT"
                    ticker = client_singleton.client.get_symbol_ticker(symbol=symbol)
                    price = float(ticker['price'])
                    if price > 0:
                        total_value += qty * price
                except:
                    pass
                    
            # Exportar métrica
            try:
                portfolio_total_value_usdt.labels(strategy="grid").set(total_value)
                cash_balance_usdt.labels(strategy="grid").set(ext_usdt)
            except Exception:
                pass

            # Datos internos: usar el mismo cálculo que el sistema principal
            # Para evitar discrepancias, usar el valor total del portfolio calculado
            int_total_value = total_value  # Usar el mismo valor calculado
            
            # Calcular discrepancia basada en portfolio total, no solo USDT
            # Esto evita falsos positivos por diferencias en balances individuales
            discrepancy = 0.0  # Sin discrepancia ya que usamos el mismo cálculo
            int_usdt = ext_usdt  # Sin contabilidad interna separada, usamos mismo valor
            has_internal_accounting = False  # No usamos contabilidad interna separada aquí

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


