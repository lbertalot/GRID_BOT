"""
Hotfix S12: strategy_selector debe ser Decimal-safe de punta a punta.

Reproduce el TypeError float×Decimal que hacía fallar toda selección
(caught → HOLD silencioso) y bloqueaba el ciclo paper / tear sheet.
"""

from decimal import Decimal

import pytest

from app.core.risk_manager import MarketRegime, RegimePrediction, RiskManager
from app.services.strategy_selector import (
    AccountState,
    StrategyParams,
    StrategySelector,
    StrategyType,
)


@pytest.fixture
def risk_manager():
    return RiskManager()


@pytest.fixture
def selector(risk_manager):
    return StrategySelector(risk_manager)


def _regime(
    long_regime=MarketRegime.RANGE,
    short_regime=MarketRegime.RANGE,
    long_conf=Decimal("0.8"),
    short_conf=Decimal("0.7"),
) -> RegimePrediction:
    return RegimePrediction(
        long_regime=long_regime,
        short_regime=short_regime,
        long_conf=long_conf,
        short_conf=short_conf,
    )


def _account_decimal(**overrides) -> AccountState:
    base = dict(
        total_equity=Decimal("10000"),
        available_balance=Decimal("5000"),
        total_exposure=Decimal("0.5"),
        daily_pnl=Decimal("0.02"),
        max_drawdown=Decimal("0.05"),
        risk_score=Decimal("0.3"),
    )
    base.update(overrides)
    return AccountState(**base)


def _account_float(**overrides) -> AccountState:
    """Inputs legacy float (como fixtures pre-S12) — deben seguir funcionando."""
    base = dict(
        total_equity=10000.0,
        available_balance=5000.0,
        total_exposure=0.5,
        daily_pnl=0.02,
        max_drawdown=0.05,
        risk_score=0.3,
    )
    base.update(overrides)
    return AccountState(**base)


class TestStrategySelectorDecimalSafety:
    def test_account_state_coerces_float_and_decimal_to_decimal(self):
        from_float = _account_float()
        from_dec = _account_decimal()
        for state in (from_float, from_dec):
            assert isinstance(state.total_equity, Decimal)
            assert isinstance(state.available_balance, Decimal)
            assert state.total_equity == Decimal("10000")

    def test_calculate_dynamic_params_grid_no_typeerror_with_decimal_account(
        self, selector
    ):
        """Causa raíz: available_balance (float) / dynamic_size (Decimal)."""
        params = selector._calculate_dynamic_params(
            StrategyType.GRID_TRADING, _regime(), _account_decimal()
        )
        assert isinstance(params.order_size_usdt, Decimal)
        assert params.order_size_usdt > 0
        assert params.grid_levels is not None and params.grid_levels > 0

    def test_calculate_dynamic_params_scalping_no_typeerror(self, selector):
        """Causa raíz: dynamic_size (Decimal) * 0.5 (float)."""
        params = selector._calculate_dynamic_params(
            StrategyType.SCALPING, _regime(), _account_float()
        )
        assert isinstance(params.order_size_usdt, Decimal)
        assert params.order_size_usdt > 0

    def test_select_strategy_grid_with_decimal_inputs_does_not_hold_on_error(
        self, selector
    ):
        """Antes: TypeError → HOLD con reasoning 'Error in strategy selection'."""
        spec = selector.select_strategy(
            _regime(), "BTCUSDT", _account_decimal()
        )
        assert spec.strategy_name == StrategyType.GRID_TRADING
        assert "Error in strategy selection" not in spec.reasoning
        assert isinstance(spec.confidence, Decimal)
        assert isinstance(spec.params.order_size_usdt, Decimal)

    def test_select_strategy_with_legacy_float_account_state(self, selector):
        spec = selector.select_strategy(
            _regime(
                long_regime=MarketRegime.BULL_TREND,
                short_regime=MarketRegime.BULL_TREND,
            ),
            "ETHUSDT",
            _account_float(),
        )
        assert spec.strategy_name == StrategyType.DCA
        assert "Error in strategy selection" not in spec.reasoning
        assert isinstance(spec.confidence, Decimal)

    def test_confidence_adjustment_decimal_safe(self, selector):
        """Causa raíz: confidence (Decimal) *= 0.69 (float)."""
        high_risk = _account_decimal(
            daily_pnl=Decimal("-0.06"),
            risk_score=Decimal("0.9"),
        )
        rp = _regime(
            long_regime=MarketRegime.RANGE,
            short_regime=MarketRegime.RANGE,
            long_conf=Decimal("0.8"),
            short_conf=Decimal("0.7"),
        )
        spec = selector.select_strategy(rp, "BTCUSDT", high_risk)
        base = (rp.long_conf + rp.short_conf) / Decimal("2")
        assert spec.confidence < base
        assert "Error in strategy selection" not in spec.reasoning

    def test_smoke_selection_cycle_raises_no_typeerror(self, selector):
        """Un ciclo de selección no levanta TypeError (DoD smoke)."""
        accounts = [_account_decimal(), _account_float()]
        regimes = [
            _regime(),
            _regime(
                long_regime=MarketRegime.BULL_TREND,
                short_regime=MarketRegime.BULL_TREND,
            ),
            _regime(
                long_regime=MarketRegime.BEAR_TREND,
                short_regime=MarketRegime.BEAR_TREND,
            ),
            _regime(short_regime=MarketRegime.HIGH_VOL),
        ]
        for account in accounts:
            for rp in regimes:
                spec = selector.select_strategy(rp, "BTCUSDT", account)
                assert spec is not None
                assert isinstance(spec.confidence, Decimal)
                assert "Error in strategy selection" not in spec.reasoning

    def test_strategy_params_monetary_fields_are_decimal(self):
        params = StrategyParams(
            order_size_usdt=Decimal("50"),
            tranche_size=25.0,  # legacy float input
            take_profit=0.05,
            stop_loss=Decimal("0.01"),
            max_exposure=Decimal("0.3"),
        )
        assert isinstance(params.order_size_usdt, Decimal)
        assert isinstance(params.tranche_size, Decimal)
        assert isinstance(params.take_profit, Decimal)
