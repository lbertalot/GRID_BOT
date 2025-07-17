from typing import Any

def trailing_stop_strategy(*, price_history: list[float], balances: dict[str, float], params: dict[str, Any]) -> dict:
    """
    Estrategia Trailing Stop:
    - params debe incluir: 'trailing_pct' (ej: 0.01 para 1%)
    - price_history: lista de precios ordenados (más antiguo a más reciente)
    - balances: saldos actuales
    """
    if not price_history:
        return {"action": "HOLD", "quantity": 0, "reason": "Sin histórico de precios"}
    trailing_pct = params.get('trailing_pct', 0.01)
    max_price = max(price_history)
    current_price = price_history[-1]
    trigger_price = max_price * (1 - trailing_pct)
    if current_price < trigger_price:
        return {"action": "SELL", "quantity": balances.get('BTC', 0), "reason": f"Trailing stop activado: {current_price} < {trigger_price}"}
    return {"action": "HOLD", "quantity": 0, "reason": "No se activa trailing stop"} 