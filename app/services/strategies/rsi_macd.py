from typing import Any
import numpy as np

def rsi(prices: list[float], period: int = 14) -> float:
    if len(prices) < period + 1:
        return 50.0
    deltas = np.diff(prices)
    seed = deltas[:period]
    up = seed[seed > 0].sum() / period
    down = -seed[seed < 0].sum() / period
    rs = up / down if down != 0 else 0
    return 100. - 100. / (1. + rs)

def macd(prices: list[float], fast: int = 12, slow: int = 26, signal: int = 9) -> tuple[float, float]:
    if len(prices) < slow + signal:
        return 0.0, 0.0
    exp1 = np.convolve(prices, np.ones(fast)/fast, mode='valid')
    exp2 = np.convolve(prices, np.ones(slow)/slow, mode='valid')
    macd_line = exp1[-1] - exp2[-1]
    signal_line = np.convolve([macd_line], np.ones(signal)/signal, mode='valid')[-1]
    return macd_line, signal_line

def rsi_macd_strategy(*, price_history: list[float], balances: dict[str, float], params: dict[str, Any]) -> dict:
    period = params.get('rsi_period', 14)
    rsi_value = rsi(price_history, period)
    macd_line, signal_line = macd(price_history)
    reason = f"RSI={rsi_value:.2f}, MACD={macd_line:.2f}, Signal={signal_line:.2f}"
    if rsi_value < 30 and macd_line > signal_line:
        return {"action": "BUY", "quantity": balances.get('USDT', 0) / price_history[-1], "reason": reason}
    if rsi_value > 70 and macd_line < signal_line and balances.get('BTC', 0) > 0:
        return {"action": "SELL", "quantity": balances.get('BTC', 0), "reason": reason}
    return {"action": "HOLD", "quantity": 0, "reason": reason} 