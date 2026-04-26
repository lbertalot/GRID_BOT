import os
import sys
import pytest
from types import SimpleNamespace

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.strategy_manager import StrategyManager, AdaptationPolicy


class DummyML:
    def __init__(self, label: int, proba: float):
        self.label = label
        self.proba = proba

    async def predict_regime(self, symbol: str, interval: str = "1m", limit: int = 60):
        return SimpleNamespace(label=self.label, proba=self.proba)


@pytest.mark.asyncio
async def test_strategy_manager_adapts_bullish():
    policy = AdaptationPolicy()
    ml = DummyML(label=1, proba=0.7)
    sm = StrategyManager(policy=policy, ml_engine=ml)
    manager = SimpleNamespace(
        config=SimpleNamespace(
            assets={
                "BTCUSDT": SimpleNamespace(
                    symbol="BTCUSDT",
                    grids=5,
                    quantity=0.01,
                    min_price=100,
                    max_price=200,
                    is_active=True,
                )
            }
        ),
        trading_history=[],
    )
    changes = await sm.adapt_manager(manager)
    assert "BTCUSDT" in changes and changes["BTCUSDT"]["grids"] >= 5


@pytest.mark.asyncio
async def test_strategy_manager_adapts_bearish():
    policy = AdaptationPolicy()
    ml = DummyML(label=0, proba=0.7)
    sm = StrategyManager(policy=policy, ml_engine=ml)
    manager = SimpleNamespace(
        config=SimpleNamespace(
            assets={
                "BTCUSDT": SimpleNamespace(
                    symbol="BTCUSDT",
                    grids=5,
                    quantity=0.01,
                    min_price=100,
                    max_price=200,
                    is_active=True,
                )
            }
        ),
        trading_history=[],
    )
    changes = await sm.adapt_manager(manager)
    assert "BTCUSDT" in changes and changes["BTCUSDT"]["grids"] <= 5
