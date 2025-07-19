import pytest
from app.services.strategies.trailing_stop import trailing_stop_strategy
from app.services.strategies.scalping import scalping_strategy
from app.services.strategies.rsi_macd import rsi_macd_strategy

@pytest.mark.parametrize("strategy,price_history,balances,params,expected_action", [
    (trailing_stop_strategy, [100, 105, 110, 108, 107, 106, 104], {"BTC": 0.01}, {"trailing_pct": 0.05}, "SELL"),
    (trailing_stop_strategy, [100, 105, 110, 112, 115], {"BTC": 0.01}, {"trailing_pct": 0.05}, "HOLD"),
    (scalping_strategy, [100, 99, 98], {"USDT": 100}, {}, "BUY"),
    (scalping_strategy, [100, 101, 102], {"BTC": 0.01}, {}, "SELL"),
    (scalping_strategy, [100, 101, 100], {"BTC": 0.01}, {}, "BUY"),
    (rsi_macd_strategy, [100]*30, {"USDT": 100}, {}, "HOLD"),
])
def test_strategies(strategy, price_history, balances, params, expected_action):
    result = strategy(price_history=price_history, balances=balances, params=params)
    assert result["action"] == expected_action 