from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List

from sqlalchemy.orm import Session

from app.models.trade import Trade
from app.core.metrics import (
    profit_total_usdt,
    profit_by_asset_usdt,
    roi_by_asset_percent,
)


def _d(value) -> Decimal:
    """Convierte un valor numérico a Decimal de forma segura."""
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def settle_pnl_on_sell(
    db: Session, symbol: str, sell_qty, sell_price
) -> Dict[str, float]:
    """
    Cierra BUYs abiertos (FIFO) al ejecutar un SELL y computa PnL realizado.
    Retorna resumen con pnl_realized y qty_closed.
    """
    remaining_qty = _d(sell_qty)
    pnl_realized = Decimal("0")
    qty_closed = Decimal("0")
    sell_price_d = _d(sell_price)

    # BUYs abiertos: exit_price is NULL
    open_buys: List[Trade] = (
        db.query(Trade)
        .filter(
            Trade.symbol == symbol.upper(),
            Trade.side == "BUY",
            Trade.exit_price == None,
        )  # noqa: E711
        .order_by(Trade.timestamp.asc())
        .all()
    )

    epsilon = Decimal("1e-12")
    for buy in open_buys:
        if remaining_qty <= 0:
            break
        buy_qty = _d(buy.quantity)
        close_qty = min(remaining_qty, buy_qty)
        entry_price = _d(buy.entry_price)
        trade_pnl = (sell_price_d - entry_price) * close_qty

        if close_qty >= buy_qty - epsilon:
            buy.exit_price = sell_price_d
            buy.profit_loss = (sell_price_d - entry_price) * buy_qty
        else:
            remaining_in_buy = buy_qty - close_qty
            buy.quantity = remaining_in_buy
            closed = Trade(
                symbol=buy.symbol,
                side=buy.side,
                quantity=close_qty,
                entry_price=entry_price,
                exit_price=sell_price_d,
                profit_loss=trade_pnl,
            )
            db.add(closed)

        pnl_realized += trade_pnl
        qty_closed += close_qty
        remaining_qty -= close_qty

    db.commit()

    return {
        "pnl_realized": float(pnl_realized),
        "qty_closed": float(qty_closed),
    }


def recompute_profit_metrics(db: Session, strategy: str = "grid") -> None:
    """
    Recalcula métricas de profit agregadas desde DB.
    ROI por activo se deja en 0 si no hay baseline de capital invertido.
    """
    rows: List[Trade] = db.query(Trade).filter(Trade.profit_loss != None).all()  # noqa: E711
    total_profit = sum(_d(t.profit_loss) for t in rows)
    profit_total_usdt.labels(strategy=strategy).set(float(total_profit))

    by_asset: Dict[str, Decimal] = {}
    for t in rows:
        asset = (t.symbol or "").replace("USDT", "") or t.symbol
        by_asset[asset] = by_asset.get(asset, Decimal("0")) + _d(t.profit_loss)

    for asset, profit in by_asset.items():
        profit_by_asset_usdt.labels(asset=asset, strategy=strategy).set(float(profit))
        roi_by_asset_percent.labels(asset=asset, strategy=strategy).set(0.0)
