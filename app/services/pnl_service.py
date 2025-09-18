from __future__ import annotations

from typing import Dict, List

from sqlalchemy.orm import Session

from app.models.trade import Trade
from app.core.metrics import (
    profit_total_usdt,
    profit_by_asset_usdt,
    roi_by_asset_percent,
)


def settle_pnl_on_sell(db: Session, symbol: str, sell_qty: float, sell_price: float) -> Dict[str, float]:
    """
    Cierra BUYs abiertos (FIFO) al ejecutar un SELL y computa PnL realizado.
    Retorna resumen con pnl_realized y qty_closed.
    """
    remaining_qty = float(sell_qty)
    pnl_realized = 0.0
    qty_closed = 0.0

    # BUYs abiertos: exit_price is NULL
    open_buys: List[Trade] = (
        db.query(Trade)
        .filter(Trade.symbol == symbol.upper(), Trade.side == "BUY", Trade.exit_price == None)  # noqa: E711
        .order_by(Trade.timestamp.asc())
        .all()
    )

    for buy in open_buys:
        if remaining_qty <= 0:
            break
        close_qty = min(remaining_qty, float(buy.quantity))
        entry_price = float(buy.entry_price)
        trade_pnl = (sell_price - entry_price) * close_qty

        # Cerrar totalmente el trade cuando cantidades coinciden; en caso parcial, registrar PnL proporcional
        if close_qty >= float(buy.quantity) - 1e-12:
            buy.exit_price = sell_price
            buy.profit_loss = (sell_price - entry_price) * float(buy.quantity)
        else:
            # Para parcial: ajustar cantidad y crear un registro cerrado proporcional
            remaining_in_buy = float(buy.quantity) - close_qty
            buy.quantity = remaining_in_buy
            closed = Trade(
                symbol=buy.symbol,
                side=buy.side,
                quantity=close_qty,
                entry_price=entry_price,
                exit_price=sell_price,
                profit_loss=trade_pnl,
            )
            db.add(closed)

        pnl_realized += trade_pnl
        qty_closed += close_qty
        remaining_qty -= close_qty

    db.commit()

    return {"pnl_realized": pnl_realized, "qty_closed": qty_closed}


def recompute_profit_metrics(db: Session, strategy: str = "grid") -> None:
    """
    Recalcula métricas de profit agregadas desde DB.
    ROI por activo se deja en 0 si no hay baseline de capital invertido.
    """
    # Suma de PnL realizado
    rows: List[Trade] = db.query(Trade).filter(Trade.profit_loss != None).all()  # noqa: E711
    total_profit = sum(float(t.profit_loss or 0.0) for t in rows)
    profit_total_usdt.labels(strategy=strategy).set(total_profit)

    # Por activo
    by_asset: Dict[str, float] = {}
    for t in rows:
        asset = (t.symbol or "").replace("USDT", "") or t.symbol
        by_asset[asset] = by_asset.get(asset, 0.0) + float(t.profit_loss or 0.0)

    for asset, profit in by_asset.items():
        profit_by_asset_usdt.labels(asset=asset, strategy=strategy).set(profit)
        # ROI por activo requiere baseline; publicamos 0.0 por ahora
        roi_by_asset_percent.labels(asset=asset, strategy=strategy).set(0.0)


