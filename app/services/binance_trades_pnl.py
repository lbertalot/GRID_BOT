"""
Extractor y calculadora de PnL/ROI usando trades "puros" de Binance.

Calcula PnL realizado por símbolo con emparejamiento FIFO de lotes (compras → ventas).
Convierte comisiones a USDT cuando es necesario.
"""

from __future__ import annotations

from typing import Dict, List, Tuple
import logging

from app.services.binance_client_singleton import get_binance_client_singleton

logger = logging.getLogger(__name__)


def _get_quote_asset(symbol: str) -> str:
    symbol = symbol.upper()
    for quote in ("USDT", "BUSD", "USDC", "TUSD", "FDUSD", "DAI", "BTC", "ETH", "BNB"):
        if symbol.endswith(quote):
            return quote
    return "USDT"


def _convert_to_usdt(amount: float, asset: str) -> float:
    """Convierte un monto en un asset dado a USDT usando precios spot actuales.
    Para stablecoins 1:1 retorna el mismo valor.
    """
    asset = (asset or "").upper()
    if amount == 0.0 or not asset:
        return 0.0
    if asset in {"USDT", "BUSD", "USDC", "TUSD", "FDUSD", "DAI"}:
        return amount
    try:
        client = get_binance_client_singleton()
        price = client.get_symbol_price(f"{asset}USDT")
        return amount * (price or 0.0)
    except Exception as e:
        logger.warning(f"Fallo convirtiendo {amount} {asset} a USDT: {e}")
        return 0.0


def _commission_usdt(commission: float, commission_asset: str, symbol: str, side: str) -> float:
    if commission is None or commission == 0.0:
        return 0.0
    quote = _get_quote_asset(symbol)
    if commission_asset.upper() == quote:
        return commission
    return _convert_to_usdt(commission, commission_asset)


def _fifo_realized_pnl_usdt(trades: List[dict], symbol: str) -> Tuple[float, float]:
    """Calcula PnL realizado y capital invertido (compras) en USDT para una lista de trades.
    Retorna (profit_total_usdt, invested_usdt).
    """
    # Ordenar por tiempo ascendente
    trades_sorted = sorted(trades, key=lambda t: t.get("time", 0))
    buy_lots: List[Tuple[float, float]] = []  # (qty_restante, costo_unit_usdt)
    profit_total = 0.0
    invested_total = 0.0

    for t in trades_sorted:
        qty = float(t.get("qty") or t.get("quantity") or 0.0)
        price = float(t.get("price") or 0.0)
        is_buyer = bool(t.get("isBuyer"))
        comm = float(t.get("commission") or 0.0)
        comm_asset = (t.get("commissionAsset") or "USDT").upper()

        # Valor en USDT de la línea (ignora fees aquí)
        line_value_usdt = qty * price

        if is_buyer:
            # Costo unitario ajustado por comisión (sumar fee al costo)
            fee_usdt = _commission_usdt(comm, comm_asset, symbol, "BUY")
            cost_usdt = line_value_usdt + fee_usdt
            unit_cost = cost_usdt / qty if qty > 0 else 0.0
            buy_lots.append((qty, unit_cost))
            invested_total += cost_usdt
        else:
            # Venta: realizar PnL contra FIFO y descontar comisión
            qty_to_match = qty
            revenue_usdt = line_value_usdt
            realized = 0.0
            while qty_to_match > 0 and buy_lots:
                lot_qty, lot_unit_cost = buy_lots[0]
                take = min(qty_to_match, lot_qty)
                realized += (price - lot_unit_cost) * take
                lot_qty -= take
                qty_to_match -= take
                if lot_qty <= 0:
                    buy_lots.pop(0)
                else:
                    buy_lots[0] = (lot_qty, lot_unit_cost)
            # Descontar comisión de la venta del PnL
            fee_usdt = _commission_usdt(comm, comm_asset, symbol, "SELL")
            profit_total += realized - fee_usdt

    return profit_total, invested_total


def compute_binance_pnl_and_roi(allowed_symbols: List[str]) -> Tuple[float, float, float]:
    """Obtiene trades de Binance y calcula (profit_total_usdt, invested_usdt, roi_total_pct)."""
    client = get_binance_client_singleton().client
    if client is None:
        return 0.0, 0.0, 0.0
    total_profit = 0.0
    total_invested = 0.0
    for symbol in allowed_symbols:
        try:
            trades = client.get_my_trades(symbol=symbol)
            p, inv = _fifo_realized_pnl_usdt(trades, symbol)
            total_profit += p
            total_invested += inv
        except Exception as e:
            logger.warning(f"No se pudo obtener/calc PnL para {symbol}: {e}")
    roi_pct = (total_profit / total_invested * 100.0) if total_invested > 0 else 0.0
    return total_profit, total_invested, roi_pct


