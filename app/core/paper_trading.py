#!/usr/bin/env python3
"""
Sistema de Paper Trading para GridBot V2.5.

Desde S10 (Track H) este sistema **dejó de llevar su propia contabilidad**: es un
adaptador sobre `app.core.paper_equity_ledger`, la única fuente de verdad del cash,
el inventario, los costos y la serie de equity mark-to-market del modo paper
(gap I-4 de `Docs/engineering/tear-sheet-spec.md`: había tres simuladores paper
incoherentes que producían equities distintos).

Qué cambia, y por qué importa para el tear sheet del 31/08:

- **Las comisiones se restan de verdad.** Antes el balance paper ignoraba fees y
  slippage, así que un round-trip a precio plano daba PnL cero en lugar de −24 bps.
  El PnL paper estaba inflado por construcción (gap I-5, I-6).
- **El equity se marca a mercado.** `E_t = cash_t + Σ qty_a × mid_a`, con el precio
  observado que se inyecta; sin precio no se marca (gate A6). Antes el balance era
  un float que sólo se movía por notional (gap I-3, I-7).
- **Los ciclos de grid se cuentan.** Compra y venta emparejadas FIFO con `cycle_id`
  (gap I-8), insumo del volumen de evidencia del gate B4.
- **La performance se mide sobre la serie diaria de equity, nunca sobre el PnL
  realizado de ciclos.** En un grid todo ciclo cerrado es ganador por diseño y la
  pérdida vive en el inventario: `total_pnl` de este resumen sale de equity MtM.

La API pública mantiene `float` porque sus consumidores (API, monitoreo, tasks)
son legacy; la conversión a `Decimal` ocurre en el borde y adentro todo es
`Decimal` (regla `10-financial-integrity`). Paper-only: no envía órdenes.
"""

import logging
import json
import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Mapping, Optional, Tuple

from app.core.paper_equity_ledger import (
    MarkPriceUnavailable,
    PaperEquityLedger,
    PaperEquitySeries,
    PaperLedgerError,
    compute_paper_portfolio_value,
    get_paper_equity_series,
    get_paper_ledger,
    to_money,
)

logger = logging.getLogger(__name__)

LEGACY_STATE_FILE = "paper_trading_state.json"


def _money_str(value: Decimal) -> str:
    normalized = value.normalize()
    return "0" if normalized == 0 else format(normalized, "f")


class PaperTradingSystem:
    """
    Simulador paper sobre el ledger de equity mark-to-market.

    No mantiene balances propios: cash, inventario y costos se leen del ledger.
    """

    def __init__(
        self,
        initial_balance: float = 1000.0,
        state_file: Optional[str] = None,
        ledger: Optional[PaperEquityLedger] = None,
        series: Optional[PaperEquitySeries] = None,
    ):
        self.initial_balance = initial_balance
        self.paper_trading_file = state_file or LEGACY_STATE_FILE
        self.trade_history: List[Dict] = []
        self._ledger = ledger if ledger is not None else get_paper_ledger()
        self._series = series
        self.load_state()

    # -- ledger y serie -----------------------------------------------------

    @property
    def ledger(self) -> PaperEquityLedger:
        """Fuente de verdad del equity paper."""
        return self._ledger

    @property
    def series(self) -> PaperEquitySeries:
        """Serie de equity MtM. Única vía válida para retornos, MaxDD y Calmar."""
        if self._series is None:
            self._series = get_paper_equity_series()
        return self._series

    # -- estado legacy ------------------------------------------------------

    def load_state(self) -> None:
        """
        Carga el historial legacy sólo para trazabilidad.

        Los balances del archivo legacy **no** se usan: eran floats sin fees y sin
        marcación. La contabilidad vigente vive en el ledger.
        """
        try:
            if not os.path.exists(self.paper_trading_file):
                return
            with open(self.paper_trading_file, "r") as handle:
                data = json.load(handle)
            self.trade_history = list(
                data.get("trade_history") or data.get("trades") or []
            )
            positions = data.get("positions") or {}
            reconciled = bool(data.get("legacy_positions_reconciled"))
            quarantined = data.get("_quarantined_positions")
            if positions and not reconciled and not quarantined:
                logger.warning(
                    "[PaperTrading] El estado legacy tiene %s posiciones que no se "
                    "importan al ledger MtM: reconciliar antes de abrir la ventana "
                    "del tear sheet (scripts/quarantine_legacy_paper_positions.py)",
                    len(positions),
                )
            elif quarantined or reconciled:
                logger.info(
                    "[PaperTrading] Legacy positions ya cuarentenadas/reconciliadas; "
                    "SoT = PaperEquityLedger (no se importan al MtM)"
                )
        except Exception as exc:
            logger.error("Error cargando estado de paper trading: %s", exc)

    def save_state(self) -> None:
        """Persiste el archivo legacy; el ledger se persiste solo (JSON versionado)."""
        try:
            data = {
                "current_balance": self.current_balance,
                "positions": self.positions,
                "trade_history": self.trade_history,
                "last_updated": datetime.now(timezone.utc).isoformat(),
                "source_of_truth": "app.core.paper_equity_ledger",
            }
            with open(self.paper_trading_file, "w") as handle:
                json.dump(data, handle, indent=2)
        except Exception as exc:
            logger.error("Error guardando estado de paper trading: %s", exc)

    @property
    def current_balance(self) -> float:
        """Cash disponible. **No** es el equity: el equity incluye inventario."""
        return float(self._ledger.cash)

    @property
    def positions(self) -> Dict[str, Dict[str, float]]:
        positions: Dict[str, Dict[str, float]] = {}
        for symbol in self._ledger.symbols():
            open_cycles = self._ledger.open_cycles(symbol)
            quantity = self._ledger.position(symbol)
            cost_basis = sum((c.cost_basis_open for c in open_cycles), Decimal("0"))
            positions[symbol] = {
                "quantity": float(quantity),
                "avg_price": float(cost_basis / quantity) if quantity > 0 else 0.0,
                "unrealized_pnl": 0.0,
            }
        return positions

    def get_balance(self) -> float:
        return self.current_balance

    def get_positions(self) -> Dict:
        return self.positions

    def get_trade_history(self) -> List[Dict]:
        return list(self.trade_history)

    # -- órdenes ------------------------------------------------------------

    def place_buy_order(
        self,
        symbol: str,
        quantity: float,
        price: float,
        order_type: str = "LIMIT",
        grid_level: Optional[int] = None,
    ) -> Dict:
        """Compra paper: descuenta notional **y costos** del cash y abre un ciclo."""
        try:
            fill = self._ledger.record_buy(
                symbol,
                to_money(str(quantity), field_name="quantity"),
                to_money(str(price), field_name="price"),
                order_type=order_type,
                grid_level=grid_level,
            )
        except (PaperLedgerError, ValueError) as exc:
            logger.warning("Orden de compra paper rechazada: %s", exc)
            return {"success": False, "error": str(exc), "order_id": None}

        self._append_trade(fill)
        self.save_state()
        logger.info(
            "📈 Paper BUY %s %s @ %s = %s USDT (fee %s + slippage %s)",
            fill.symbol,
            _money_str(fill.quantity),
            _money_str(fill.price),
            _money_str(fill.notional_usdt),
            _money_str(fill.commission_usdt),
            _money_str(fill.slippage_usdt),
        )
        return {
            "success": True,
            "order_id": fill.fill_id,
            "executed_quantity": float(fill.quantity),
            "executed_price": float(fill.price),
            "total_cost": float(
                fill.notional_usdt + fill.commission_usdt + fill.slippage_usdt
            ),
            "commission_usdt": _money_str(fill.commission_usdt),
            "commission_asset": fill.commission_asset,
            "slippage_usdt": _money_str(fill.slippage_usdt),
            "cycle_id": fill.cycle_id,
            "balance_after": self.current_balance,
        }

    def place_sell_order(
        self,
        symbol: str,
        quantity: float,
        price: float,
        order_type: str = "LIMIT",
    ) -> Dict:
        """Venta paper: acredita el notional neto de costos y cierra ciclos FIFO."""
        try:
            fill = self._ledger.record_sell(
                symbol,
                to_money(str(quantity), field_name="quantity"),
                to_money(str(price), field_name="price"),
                order_type=order_type,
            )
        except (PaperLedgerError, ValueError) as exc:
            logger.warning("Orden de venta paper rechazada: %s", exc)
            return {"success": False, "error": str(exc), "order_id": None}

        matched = [
            cycle
            for cycle in self._ledger.cycles
            if cycle.cycle_id in fill.cycle_ids
        ]
        realized_gross = sum((c.gross_pnl_usdt for c in matched), Decimal("0"))
        realized_net = sum((c.net_pnl_usdt for c in matched), Decimal("0"))

        self._append_trade(
            fill, realized_gross=realized_gross, realized_net=realized_net
        )
        self.save_state()
        logger.info(
            "📉 Paper SELL %s %s @ %s (PnL neto de ciclos %s USDT, costos %s)",
            fill.symbol,
            _money_str(fill.quantity),
            _money_str(fill.price),
            _money_str(realized_net),
            _money_str(fill.commission_usdt + fill.slippage_usdt),
        )
        return {
            "success": True,
            "order_id": fill.fill_id,
            "executed_quantity": float(fill.quantity),
            "executed_price": float(fill.price),
            "total_revenue": float(
                fill.notional_usdt - fill.commission_usdt - fill.slippage_usdt
            ),
            "realized_pnl": float(realized_net),
            "realized_pnl_gross": float(realized_gross),
            "commission_usdt": _money_str(fill.commission_usdt),
            "slippage_usdt": _money_str(fill.slippage_usdt),
            "closed_cycle_ids": list(fill.cycle_ids),
            "closed_cycles": self._ledger.closed_cycle_count,
            "balance_after": self.current_balance,
        }

    def _append_trade(
        self,
        fill,
        realized_gross: Decimal = Decimal("0"),
        realized_net: Decimal = Decimal("0"),
    ) -> None:
        self.trade_history.append(
            {
                "timestamp": fill.executed_at.isoformat(),
                "symbol": fill.symbol,
                "side": fill.side,
                "quantity": float(fill.quantity),
                "price": float(fill.price),
                "notional_usdt": _money_str(fill.notional_usdt),
                "commission_usdt": _money_str(fill.commission_usdt),
                "commission_asset": fill.commission_asset,
                "slippage_usdt": _money_str(fill.slippage_usdt),
                "cycle_id": fill.cycle_id,
                "cycle_ids": list(fill.cycle_ids),
                "realized_pnl_gross": _money_str(realized_gross),
                "realized_pnl": _money_str(realized_net),
                "balance_after": self.current_balance,
            }
        )

    # -- marcación a mercado ------------------------------------------------

    def _marks(
        self, current_prices: Optional[Mapping[str, Any]] = None
    ) -> Dict[str, Decimal]:
        """Precios de marcación para los símbolos con inventario."""
        provided = (
            {
                str(symbol).upper(): to_money(str(price), field_name=f"mark[{symbol}]")
                for symbol, price in current_prices.items()
            }
            if current_prices
            else {}
        )
        return {
            symbol: provided[symbol]
            for symbol in self._ledger.symbols()
            if symbol in provided
        }

    def mark_to_market(
        self,
        current_prices: Optional[Mapping[str, Any]] = None,
        at: Optional[datetime] = None,
        record: bool = True,
    ) -> Optional[Decimal]:
        """
        Marca el equity paper y lo registra en la serie.

        Con `current_prices` usa esos precios (tests, simulaciones); sin ellos va al
        ticker real vía `compute_paper_portfolio_value` (gate A6). Retorna `None` si
        falta algún precio: un hueco declarado es mejor que un equity inventado.
        """
        if current_prices is None:
            payload = compute_paper_portfolio_value(
                ledger=self._ledger, series=self._series, at=at, record=record
            )
            return to_money(str(payload["total_value_usdt"])) if payload else None

        marks = self._marks(current_prices)
        try:
            breakdown = self._ledger.equity_breakdown(marks)
        except MarkPriceUnavailable as exc:
            logger.error("[PaperTrading] Marca omitida por falta de precio: %s", exc)
            return None
        if record:
            self.series.record(
                breakdown["equity"],
                at=at,
                cash=breakdown["cash"],
                inventory_value=breakdown["inventory_value"],
                deployed_capital=self._ledger.deployed_capital,
            )
        return breakdown["equity"]

    def daily_closes(self) -> List[Tuple[datetime, Decimal]]:
        """Cierres diarios de equity anclados a 00:00 UTC."""
        return self.series.daily_closes()

    def daily_returns(self) -> List[Decimal]:
        """Retornos diarios sobre equity MtM: el insumo canónico del tear sheet."""
        return self.series.daily_returns()

    def update_positions_pnl(
        self, current_prices: Optional[Mapping[str, Any]] = None
    ) -> float:
        """PnL no realizado del inventario abierto a los precios provistos."""
        try:
            return float(self._ledger.unrealized_pnl_usdt(self._marks(current_prices)))
        except MarkPriceUnavailable as exc:
            logger.warning("[PaperTrading] PnL no realizado incompleto: %s", exc)
            return 0.0

    def get_portfolio_summary(
        self, current_prices: Optional[Mapping[str, Any]] = None
    ) -> Dict:
        """
        Resumen paper. La cifra que manda es `equity_mtm_usdt`.

        `total_pnl` se calcula sobre equity MtM, no sobre ciclos cerrados: medir un
        grid por PnL realizado es una mentira mecánica (tear-sheet-spec §1.2-B1).
        `equity_mtm_usdt` es `None` si falta algún precio de marcación.
        """
        marks = self._marks(current_prices)
        ledger = self._ledger
        cost_ratio = ledger.cost_ratio()

        summary: Dict[str, Any] = {
            "initial_balance": float(ledger.initial_cash),
            "current_balance": self.current_balance,
            "deployed_capital_usdt": _money_str(ledger.deployed_capital),
            "fees_paid_usdt": _money_str(ledger.fees_total_usdt),
            "slippage_paid_usdt": _money_str(ledger.slippage_total_usdt),
            "total_costs_usdt": _money_str(
                ledger.fees_total_usdt + ledger.slippage_total_usdt
            ),
            "cost_round_trip_bps": _money_str(ledger.cost_model.round_trip_bps),
            "cost_ratio": _money_str(cost_ratio) if cost_ratio is not None else None,
            "total_realized_pnl_gross": float(ledger.realized_gross_pnl_usdt),
            "total_realized_pnl_net": float(ledger.realized_net_pnl_usdt),
            "closed_cycles": ledger.closed_cycle_count,
            "open_cycles": ledger.open_cycle_count,
            "total_trades": len(self.trade_history),
            "equity_source": "mark_to_market",
            "daily_closes": len(self.series.daily_closes()),
        }

        try:
            breakdown = ledger.equity_breakdown(marks)
        except MarkPriceUnavailable as exc:
            logger.warning(
                "[PaperTrading] Resumen sin equity MtM por falta de precio: %s", exc
            )
            summary.update(
                {
                    "equity_mtm_usdt": None,
                    "pnl_mtm_usdt": None,
                    "total_pnl": None,
                    "total_pnl_pct": None,
                    "total_unrealized_pnl": None,
                    "positions": [],
                    "open_positions": ledger.open_cycle_count,
                    "mark_prices_missing": True,
                }
            )
            return summary

        equity = breakdown["equity"]
        pnl_mtm = equity - ledger.initial_cash
        positions_summary = []
        for symbol, position in breakdown["positions"].items():
            cost_basis = sum(
                (c.cost_basis_open for c in ledger.open_cycles(symbol)), Decimal("0")
            )
            unrealized = position["value"] - cost_basis
            positions_summary.append(
                {
                    "symbol": symbol,
                    "quantity": float(position["quantity"]),
                    "avg_price": float(cost_basis / position["quantity"])
                    if position["quantity"] > 0
                    else 0.0,
                    "current_price": float(position["mark"]),
                    "market_value": float(position["value"]),
                    "cost_basis": float(cost_basis),
                    "unrealized_pnl": float(unrealized),
                    "unrealized_pnl_pct": float(unrealized / cost_basis * 100)
                    if cost_basis > 0
                    else 0.0,
                }
            )

        summary.update(
            {
                "equity_mtm_usdt": _money_str(equity),
                "inventory_value_usdt": _money_str(breakdown["inventory_value"]),
                "pnl_mtm_usdt": _money_str(pnl_mtm),
                "total_pnl": float(pnl_mtm),
                "total_pnl_pct": float(pnl_mtm / ledger.initial_cash * 100)
                if ledger.initial_cash > 0
                else 0.0,
                "total_unrealized_pnl": float(ledger.unrealized_pnl_usdt(marks)),
                "positions": positions_summary,
                "open_positions": len(positions_summary),
                "mark_prices_missing": False,
            }
        )
        return summary

    def reset_paper_trading(self, new_balance: Optional[float] = None) -> None:
        """
        Reinicia el ledger paper.

        **Reinicia también la ventana del tear sheet**: la serie de equity vuelve a
        cero y el conteo de días limpios arranca de nuevo (gate A1/A2).
        """
        if new_balance:
            self.initial_balance = new_balance

        self._ledger = PaperEquityLedger(
            initial_cash=to_money(str(self.initial_balance)),
            deployed_capital=self._ledger.deployed_capital,
            cost_model=self._ledger.cost_model,
            storage_path=self._ledger.storage_path,
        )
        self._series = PaperEquitySeries(
            config_hash=self.series.config_hash,
            deployed_capital=self._ledger.deployed_capital,
            storage_path=self.series.storage_path,
        )
        self.trade_history = []
        self.save_state()
        logger.warning(
            "🔄 Paper trading reseteado con balance %.2f — la ventana de equity del "
            "tear sheet arranca de cero",
            self.initial_balance,
        )


# Instancia global del sistema de paper trading
paper_trading_system = PaperTradingSystem()


def get_paper_trading() -> PaperTradingSystem:
    """Función de conveniencia para obtener el sistema de paper trading"""
    return paper_trading_system


def place_paper_buy_order(symbol: str, quantity: float, price: float) -> Dict:
    """Función de conveniencia para orden de compra"""
    return paper_trading_system.place_buy_order(symbol, quantity, price)


def place_paper_sell_order(symbol: str, quantity: float, price: float) -> Dict:
    """Función de conveniencia para orden de venta"""
    return paper_trading_system.place_sell_order(symbol, quantity, price)


def get_paper_portfolio_summary(current_prices: Dict[str, float] = None) -> Dict:
    """Función de conveniencia para obtener resumen del portafolio"""
    return paper_trading_system.get_portfolio_summary(current_prices)
