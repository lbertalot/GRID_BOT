"""
Extractor y calculadora de PnL/ROI usando trades "puros" de Binance.

Calcula PnL realizado por símbolo con emparejamiento FIFO de lotes (compras → ventas).
Convierte comisiones a USDT cuando es necesario.
"""

from __future__ import annotations

from typing import Dict, List, Tuple
import logging
import time
from binance.exceptions import BinanceAPIException

from app.services.binance_client_singleton import get_binance_client_singleton

logger = logging.getLogger(__name__)

# Circuit breaker para errores -2015 (IP no autorizada)
_last_2015_error_ts: float = 0.0
_2015_error_count: int = 0
_2015_circuit_open_until: float = 0.0
_2015_COOLDOWN_SECONDS = 300  # 5 minutos
_2015_MAX_ERRORS = 3


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
    """
    Obtiene trades de Binance y calcula (profit_total_usdt, invested_usdt, roi_total_pct).
    
    Maneja errores -2015 (IP no autorizada) con circuit breaker para evitar spam de logs.
    """
    global _last_2015_error_ts, _2015_error_count, _2015_circuit_open_until
    
    client = get_binance_client_singleton().client
    if client is None:
        return 0.0, 0.0, 0.0
    
    # Verificar circuit breaker para errores -2015
    now = time.time()
    if now < _2015_circuit_open_until:
        # Circuit breaker abierto: no intentar llamadas
        logger.debug(f"Circuit breaker activo para errores -2015 (hasta {_2015_circuit_open_until - now:.0f}s)")
        return 0.0, 0.0, 0.0
    
    total_profit = 0.0
    total_invested = 0.0
    has_2015_error = False
    
    for symbol in allowed_symbols:
        try:
            trades = client.get_my_trades(symbol=symbol)
            p, inv = _fifo_realized_pnl_usdt(trades, symbol)
            total_profit += p
            total_invested += inv
        except BinanceAPIException as e:
            # Manejar específicamente error -2015 (IP no autorizada)
            if getattr(e, 'code', None) == -2015 or 'Invalid API-key, IP' in str(e):
                has_2015_error = True
                _2015_error_count += 1
                _last_2015_error_ts = now
                
                # Log solo la primera vez o cada 5 minutos
                if _2015_error_count == 1 or (now - _last_2015_error_ts) > 300:
                    logger.warning(
                        f"⚠️ Binance -2015 (IP no autorizada) para {symbol}. "
                        f"Verifica whitelist de IP en Binance. "
                        f"Circuit breaker activado por {_2015_COOLDOWN_SECONDS}s"
                    )
                    # Notificar usando el sistema del singleton
                    try:
                        from app.services.binance_client_singleton import _notify_invalid_ip
                        _notify_invalid_ip(str(e))
                    except Exception:
                        pass
                
                # Activar circuit breaker después de N errores
                if _2015_error_count >= _2015_MAX_ERRORS:
                    _2015_circuit_open_until = now + _2015_COOLDOWN_SECONDS
                    logger.warning(
                        f"🔒 Circuit breaker activado para errores -2015. "
                        f"No se intentarán más llamadas por {_2015_COOLDOWN_SECONDS}s"
                    )
                    break  # Salir del loop para evitar más intentos
            else:
                # Otros errores de API: log normal pero no activar circuit breaker
                logger.warning(f"No se pudo obtener/calc PnL para {symbol}: {e}")
        except Exception as e:
            # Errores no relacionados con API
            logger.warning(f"No se pudo obtener/calc PnL para {symbol}: {e}")
    
    # Resetear contador si no hubo errores -2015
    if not has_2015_error and _2015_error_count > 0:
        # Si pasaron más de 10 minutos sin errores, resetear contador
        if now - _last_2015_error_ts > 600:
            _2015_error_count = 0
    
    roi_pct = (total_profit / total_invested * 100.0) if total_invested > 0 else 0.0
    return total_profit, total_invested, roi_pct


