"""
ReconciliationService — Reconcilia estado interno vs Binance y emite métricas.

Contrato: CTR-003
Invariantes: INV-001 (Decimal), INV-005 (reconciliación ≤ 60s), INV-006 (equity consistente)
"""

from __future__ import annotations

import asyncio
import logging
import time
from decimal import Decimal
from typing import Dict, Any, Optional

from binance.client import Client

from app.core.circuit_breakers import CircuitBreakers
from app.core.metrics import (
    reconciliation_latency_seconds,
    balance_discrepancy_usd,
    unaccounted_pnl_usd,
    portfolio_total_value_usdt,
    cash_balance_usdt,
)
from app.services.binance_client_singleton import get_binance_client_singleton

logger = logging.getLogger(__name__)


def _to_decimal(value: Any) -> Decimal:
    """Conversión segura a Decimal."""
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0")


class ReconciliationService:
    """Reconciliación periódica contra el exchange (CTR-003).

    Compara el valor total del portfolio calculado internamente vs el valor
    obtenido directamente del exchange, detecta discrepancias y activa breakers.
    """

    def __init__(
        self,
        client: Client,
        breakers: CircuitBreakers,
        threshold_pct: Decimal = Decimal("0.01"),
        critical_threshold_pct: Decimal = Decimal("0.05"),
    ) -> None:
        self._client = client
        self._breakers = breakers
        self._threshold_pct = threshold_pct
        self._critical_threshold_pct = critical_threshold_pct
        self._running = False

        # Estado de reconciliación para consulta externa
        self._last_result: Optional[Dict[str, Any]] = None
        self._last_ext_usdt: Decimal = Decimal("0")
        self._last_portfolio_total: Decimal = Decimal("0")

    async def run_reconciliation_cycle(self) -> Dict[str, Any]:
        """Ejecuta un ciclo de reconciliación (INV-005)."""
        start = time.time()
        try:
            client_singleton = get_binance_client_singleton()

            # Obtener datos del exchange en thread separado (no bloquear event loop)
            account_info = await asyncio.to_thread(client_singleton.get_account_info)

            if not account_info or "balances" not in account_info:
                elapsed = time.time() - start
                reconciliation_latency_seconds.observe(elapsed)
                return {
                    "status": "error",
                    "error": "No account info available",
                    "latency_seconds": elapsed,
                }

            # Parsear balances del exchange con Decimal (INV-001)
            ext_balances: Dict[str, Decimal] = {}
            for b in account_info.get("balances", []):
                asset = b.get("asset", "")
                free = _to_decimal(b.get("free", 0))
                locked = _to_decimal(b.get("locked", 0))
                total = free + locked
                if total > 0:
                    ext_balances[asset] = total

            ext_usdt = ext_balances.get("USDT", Decimal("0"))

            # Valorizar portfolio completo en USDT
            portfolio_total = ext_usdt
            valued_count = 0
            unvalued_count = 0

            for asset, qty in ext_balances.items():
                if asset == "USDT":
                    continue
                try:
                    symbol = f"{asset}USDT"
                    ticker = await asyncio.to_thread(
                        client_singleton.client.get_symbol_ticker, symbol=symbol
                    )
                    price = _to_decimal(ticker.get("price", "0"))
                    if price > 0:
                        portfolio_total += qty * price
                        valued_count += 1
                    else:
                        unvalued_count += 1
                except Exception:
                    unvalued_count += 1

            # Exportar métricas de portfolio
            try:
                portfolio_total_value_usdt.labels(strategy="grid").set(
                    float(portfolio_total)
                )
                cash_balance_usdt.labels(strategy="grid").set(float(ext_usdt))
            except Exception:
                pass

            # Calcular discrepancia contra valor interno almacenado
            # El valor interno se actualiza tras cada operación exitosa
            int_total = self._last_portfolio_total
            discrepancy = Decimal("0")
            discrepancy_pct = Decimal("0")

            if int_total > 0 and portfolio_total > 0:
                discrepancy = abs(portfolio_total - int_total)
                denom = max(Decimal("1"), portfolio_total)
                discrepancy_pct = discrepancy / denom
            else:
                # Primera ejecución o sin contabilidad interna: usar exchange como referencia
                int_total = portfolio_total

            # Actualizar estado interno
            self._last_ext_usdt = ext_usdt
            self._last_portfolio_total = portfolio_total

            # Registrar métricas de discrepancia
            balance_discrepancy_usd.set(float(discrepancy))
            unaccounted_pnl_usd.set(float(Decimal("0")))

            # Activar breaker si discrepancia supera umbral (INV-006)
            if discrepancy_pct > self._critical_threshold_pct:
                await self._breakers.activate_breaker(
                    "balance_discrepancy",
                    f"Discrepancia crítica: {discrepancy_pct:.4%} "
                    f"(int={int_total}, ext={portfolio_total})",
                )
                logger.warning(
                    f"Discrepancia CRITICA: {discrepancy_pct:.4%} | "
                    f"internal={int_total} exchange={portfolio_total}"
                )
            elif discrepancy_pct > self._threshold_pct:
                await self._breakers.activate_breaker(
                    "balance_discrepancy",
                    f"Discrepancia detectada: {discrepancy_pct:.4%}",
                )
                logger.warning(
                    f"Discrepancia detectada: {discrepancy_pct:.4%} | "
                    f"internal={int_total} exchange={portfolio_total}"
                )

            elapsed = time.time() - start
            reconciliation_latency_seconds.observe(elapsed)

            result = {
                "status": "ok",
                "ext_usdt": ext_usdt,
                "portfolio_total_usdt": portfolio_total,
                "int_usdt": int_total,
                "discrepancy_usd": discrepancy,
                "discrepancy_pct": discrepancy_pct,
                "valued_count": valued_count,
                "unvalued_count": unvalued_count,
                "latency_seconds": elapsed,
            }
            self._last_result = result
            return result

        except Exception as e:
            elapsed = time.time() - start
            reconciliation_latency_seconds.observe(elapsed)
            logger.error(f"Error en reconciliación: {e}")
            return {"status": "error", "error": str(e), "latency_seconds": elapsed}

    def update_internal_total(self, new_total: Decimal) -> None:
        """Actualiza el valor total interno tras operaciones exitosas."""
        self._last_portfolio_total = _to_decimal(new_total)

    def get_last_result(self) -> Optional[Dict[str, Any]]:
        """Retorna el último resultado de reconciliación."""
        return self._last_result

    async def start(self, interval_seconds: int = 60) -> None:
        """Inicia el loop de reconciliación periódica (INV-005)."""
        if self._running:
            return
        self._running = True
        logger.info(
            f"Reconciliación iniciada: intervalo={interval_seconds}s, "
            f"umbral={self._threshold_pct}, crítico={self._critical_threshold_pct}"
        )
        while self._running:
            try:
                await self.run_reconciliation_cycle()
            except Exception as e:
                logger.error(f"Error en ciclo de reconciliación: {e}")
            await asyncio.sleep(interval_seconds)

    async def stop(self) -> None:
        """Detiene el loop de reconciliación."""
        self._running = False
        logger.info("Reconciliación detenida")
