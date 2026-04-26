from typing import Any


def scalping_strategy(
    *, price_history: list[float], balances: dict[str, float], params: dict[str, Any]
) -> dict:
    """
    Estrategia Scalping:
    - Busca micro-movimientos rápidos para operar con pequeñas ganancias.
    - params puede incluir: 'profit_target' (porcentaje de ganancia mínima), 'lookback' (número de velas a analizar)
    """
    if not price_history or len(price_history) < 2:
        return {"action": "HOLD", "quantity": 0, "reason": "Histórico insuficiente"}
    profit_target = params.get("profit_target", 0.002)  # 0.2%
    lookback = params.get("lookback", 3)
    recent_prices = price_history[-lookback:]
    min_price = min(recent_prices)
    max_price = max(recent_prices)
    current_price = price_history[-1]
    # Señal de compra si el precio actual es el mínimo reciente
    if current_price == min_price:
        return {
            "action": "BUY",
            "quantity": balances.get("USDT", 0) / current_price,
            "reason": "Scalping: precio en mínimo local",
        }
    # Señal de venta si el precio actual es el máximo reciente y hay BTC
    if current_price == max_price and balances.get("BTC", 0) > 0:
        return {
            "action": "SELL",
            "quantity": balances.get("BTC", 0),
            "reason": "Scalping: precio en máximo local",
        }
    return {
        "action": "HOLD",
        "quantity": 0,
        "reason": "No se detecta oportunidad de scalping",
    }
