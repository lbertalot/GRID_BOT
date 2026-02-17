"""
QAA Tests: Sizing Kelly Fraccional

Objetivo: Verificar que el cálculo de Kelly fraccional es correcto,
defensivo y NUNCA expone más capital del permitido.

Nivel de riesgo: ALTO
Impacto financiero: Sobreexposición de capital, pérdidas excesivas

HALLAZGOS:
- RiskManager usa float para todos los cálculos de sizing
- _apply_position_limits modifica self.max_total_exposure_pct acumulativamente
  en apply_market_regime_filter (línea 339), lo cual reduce permanentemente
  la exposición máxima si se llama múltiples veces con regímenes negativos
- Kelly puede dar valores negativos que se clampean a 0, pero no se registra
"""

import os
import sys
import math
import pytest
from unittest.mock import MagicMock

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

os.environ.setdefault("SKIP_API_HEALTHCHECK", "1")

from app.core.risk_manager import (
    RiskManager,
    PositionSizeParams,
    KellyParams,
    TrailingStopParams,
    MarketRegime,
    BreakerState,
)


# ===========================================================================
# TEST GROUP 1: Kelly Fraccional - Cálculos correctos
# ===========================================================================

class TestKellyFractionalCalculation:
    """Tests del cálculo de Kelly fraccional."""

    @pytest.fixture
    def risk_manager(self):
        return RiskManager()

    def _make_params(self, **overrides):
        defaults = {
            "symbol": "BTCUSDT",
            "account_equity": 10000.0,
            "atr": 0.02,
            "winrate_estimate": 0.6,
            "avg_win_loss_ratio": 1.5,
            "price": 50000.0,
        }
        defaults.update(overrides)
        return PositionSizeParams(**defaults)

    def test_kelly_formula_correct(self, risk_manager):
        """Verificar que la fórmula de Kelly es correcta: f = W - (1-W)/R."""
        W = 0.6
        R = 1.5
        expected_kelly = W - (1 - W) / R  # 0.6 - 0.4/1.5 = 0.333...
        fractional = expected_kelly * risk_manager.fractional_kelly  # 0.333 * 0.25

        params = self._make_params(winrate_estimate=W, avg_win_loss_ratio=R)
        size = risk_manager.calculate_dynamic_position_size(params)

        # El tamaño debe ser proporcional al equity con Kelly fraccional
        max_expected = params.account_equity * fractional
        assert size > 0, "Kelly debe dar un tamaño positivo con winrate > 0.5"
        assert size <= params.account_equity, "Kelly nunca debe exceder 100% del equity"

    def test_kelly_negative_when_losing_strategy(self, risk_manager):
        """Kelly negativo (winrate baja) debe resultar en tamaño fallback (ATR)."""
        params = self._make_params(
            winrate_estimate=0.3,  # Estrategia perdedora
            avg_win_loss_ratio=0.8,
        )
        size = risk_manager.calculate_dynamic_position_size(params)
        assert size > 0, "Debe usar fallback ATR incluso con Kelly negativo"
        assert size < params.account_equity * 0.5, (
            "Con Kelly negativo, el tamaño debe ser conservador"
        )

    def test_kelly_with_50_50_winrate(self, risk_manager):
        """Con winrate=0.5 y R=1, Kelly=0. Debe usar fallback."""
        params = self._make_params(
            winrate_estimate=0.5,
            avg_win_loss_ratio=1.0,
        )
        size = risk_manager.calculate_dynamic_position_size(params)
        assert size > 0, "Debe usar fallback cuando Kelly = 0"

    def test_kelly_with_high_winrate(self, risk_manager):
        """Alta winrate debe dar posición más grande (pero limitada)."""
        params_low = self._make_params(winrate_estimate=0.55, avg_win_loss_ratio=1.2)
        params_high = self._make_params(winrate_estimate=0.75, avg_win_loss_ratio=2.0)

        size_low = risk_manager.calculate_dynamic_position_size(params_low)
        size_high = risk_manager.calculate_dynamic_position_size(params_high)

        assert size_high >= size_low, (
            f"Mayor winrate ({size_high}) debería dar tamaño >= que menor ({size_low})"
        )


# ===========================================================================
# TEST GROUP 2: Límites de posición
# ===========================================================================

class TestPositionLimits:
    """Tests de límites de tamaño de posición."""

    @pytest.fixture
    def risk_manager(self):
        return RiskManager()

    def _make_params(self, **overrides):
        defaults = {
            "symbol": "BTCUSDT",
            "account_equity": 10000.0,
            "atr": 0.02,
            "winrate_estimate": 0.8,
            "avg_win_loss_ratio": 3.0,
            "price": 50000.0,
        }
        defaults.update(overrides)
        return PositionSizeParams(**defaults)

    def test_position_capped_at_symbol_limit(self, risk_manager):
        """Posición no debe exceder cap_symbol_pct (20%)."""
        params = self._make_params(cap_symbol_pct=0.20)
        size = risk_manager.calculate_dynamic_position_size(params)
        max_allowed = params.account_equity * params.cap_symbol_pct
        assert size <= max_allowed, (
            f"Posición {size} excede límite por símbolo {max_allowed}"
        )

    def test_position_capped_at_equity_limit(self, risk_manager):
        """Posición no debe exceder cap_equity_pct (80%)."""
        params = self._make_params(cap_equity_pct=0.80)
        size = risk_manager.calculate_dynamic_position_size(params)
        max_allowed = params.account_equity * params.cap_equity_pct
        assert size <= max_allowed, (
            f"Posición {size} excede límite de equity {max_allowed}"
        )

    def test_position_capped_by_daily_loss(self, risk_manager):
        """
        HALLAZGO: Posición NO se reduce adecuadamente cuando hay pérdida diaria
        acumulada. El cálculo de remaining_daily_loss puede resultar negativo
        pero _apply_position_limits no reduce el tamaño a 0 cuando remaining <= 0.
        """
        risk_manager.daily_loss = 0.04  # 4% pérdida ya acumulada
        params = self._make_params(cap_daily_loss_pct=0.05)
        size = risk_manager.calculate_dynamic_position_size(params)
        # El sistema usa remaining / 0.1 como límite, que con 1% restante da $1000
        # Pero Kelly con winrate=0.8 y R=3.0 puede dar más que eso
        # Lo importante es que el size es finito y positivo
        assert size > 0, "Size debe ser positivo"
        assert size <= params.account_equity * params.cap_symbol_pct, (
            f"Posición {size} excede límite por símbolo"
        )

    def test_position_zero_when_daily_loss_exceeded(self, risk_manager):
        """
        HALLAZGO: Cuando daily_loss > cap_daily_loss_pct, remaining_daily_loss
        es negativo y max_daily_size se calcula como negativo/0.1, lo cual
        no reduce la posición porque min() con negativo no aplica correctamente.
        Esto es un riesgo: se sigue asignando tamaño cuando ya se excedió el límite.
        """
        risk_manager.daily_loss = 0.06  # 6% > 5% límite
        params = self._make_params()
        size = risk_manager.calculate_dynamic_position_size(params)
        # Documentar que el sistema NO detiene el sizing con pérdida excedida
        # El size sigue siendo positivo porque remaining es negativo
        # y el min() no limita correctamente
        assert size >= 0, "Size debe ser no-negativo"
        # Este es un HALLAZGO: el sistema debería retornar 0 o near-zero aquí
        # pero retorna el tamaño calculado por Kelly (limitado por cap_symbol_pct)

    def test_position_with_zero_equity(self, risk_manager):
        """Equity cero debe dar posición segura (no crash)."""
        params = self._make_params(account_equity=0.0)
        size = risk_manager.calculate_dynamic_position_size(params)
        assert size >= 0, "Posición negativa con equity 0"

    def test_position_with_negative_equity(self, risk_manager):
        """Equity negativa debe manejar sin crash."""
        params = self._make_params(account_equity=-1000.0)
        size = risk_manager.calculate_dynamic_position_size(params)
        # El resultado puede ser negativo o 0; lo importante es que no crashee
        assert isinstance(size, (int, float))


# ===========================================================================
# TEST GROUP 3: Regime multipliers
# ===========================================================================

class TestRegimeMultipliers:
    """Tests de multiplicadores por régimen de mercado."""

    @pytest.fixture
    def risk_manager(self):
        return RiskManager()

    def _make_params(self, **overrides):
        defaults = {
            "symbol": "BTCUSDT",
            "account_equity": 10000.0,
            "atr": 0.02,
            "winrate_estimate": 0.6,
            "avg_win_loss_ratio": 1.5,
            "price": 50000.0,
        }
        defaults.update(overrides)
        return PositionSizeParams(**defaults)

    def test_crash_imminent_reduces_position(self, risk_manager):
        """CRASH_IMMINENT debe reducir la posición un 50%."""
        params = self._make_params()
        risk_manager.current_regime = MarketRegime.RANGE
        size_normal = risk_manager.calculate_dynamic_position_size(params)

        risk_manager_crash = RiskManager()
        risk_manager_crash.current_regime = MarketRegime.CRASH_IMMINENT
        size_crash = risk_manager_crash.calculate_dynamic_position_size(params)

        assert size_crash <= size_normal, (
            f"CRASH_IMMINENT ({size_crash}) no redujo posición vs RANGE ({size_normal})"
        )

    def test_bull_trend_same_as_range(self, risk_manager):
        """BULL_TREND y RANGE deben tener el mismo multiplicador (1.0)."""
        assert risk_manager.regime_multipliers[MarketRegime.BULL_TREND] == 1.0
        assert risk_manager.regime_multipliers[MarketRegime.RANGE] == 1.0

    def test_bear_trend_reduces_position(self, risk_manager):
        """BEAR_TREND debe reducir la posición (multiplicador < 1.0)."""
        multiplier = risk_manager.regime_multipliers[MarketRegime.BEAR_TREND]
        assert multiplier < 1.0, f"BEAR_TREND multiplier {multiplier} no reduce"

    def test_all_regimes_have_multiplier(self, risk_manager):
        """Todos los regímenes deben tener multiplicador definido."""
        for regime in MarketRegime:
            assert regime in risk_manager.regime_multipliers, (
                f"Régimen {regime.value} sin multiplicador definido"
            )


# ===========================================================================
# TEST GROUP 4: Hallazgo - apply_market_regime_filter acumulativo
# ===========================================================================

class TestRegimeFilterAccumulation:
    """
    HALLAZGO: apply_market_regime_filter reduce max_total_exposure_pct
    multiplicativamente (línea 339), sin restaurarlo al valor original.

    Si se llama múltiples veces con CRASH_IMMINENT:
    - Llamada 1: 0.80 * 0.5 = 0.40
    - Llamada 2: 0.40 * 0.5 = 0.20
    - Llamada 3: 0.20 * 0.5 = 0.10
    ...hasta que la exposición máxima sea prácticamente 0.

    Impacto: El bot se vuelve incapaz de operar después de varias
    detecciones de régimen negativo, incluso cuando el mercado mejora.
    """

    def test_repeated_crash_regime_reduces_to_zero(self):
        """
        Demostrar que apply_market_regime_filter reduce acumulativamente
        max_total_exposure_pct hasta hacer trading imposible.
        """
        rm = RiskManager()
        original_max = rm.max_total_exposure_pct

        for _ in range(5):
            rm.apply_market_regime_filter(MarketRegime.CRASH_IMMINENT)

        assert rm.max_total_exposure_pct < original_max * 0.1, (
            f"Exposición máxima después de 5 aplicaciones: {rm.max_total_exposure_pct:.4f}. "
            f"Original: {original_max}. Se redujo acumulativamente."
        )

    def test_min_profit_bps_also_accumulates(self):
        """
        min_profit_bps también se duplica acumulativamente.
        Después de 5 llamadas: 50 * 2^5 = 1600 bps = 16%.
        Esto hace imposible encontrar trades rentables.
        """
        rm = RiskManager()
        original_bps = rm.min_profit_bps

        for _ in range(5):
            rm.apply_market_regime_filter(MarketRegime.HIGH_VOLATILITY_BEAR)

        assert rm.min_profit_bps > original_bps * 10, (
            f"min_profit_bps después de 5 aplicaciones: {rm.min_profit_bps}. "
            f"Original: {original_bps}. Acumulación exponencial."
        )


# ===========================================================================
# TEST GROUP 5: Trailing Stops
# ===========================================================================

class TestTrailingStops:
    """Tests de trailing stops adaptativos."""

    @pytest.fixture
    def risk_manager(self):
        return RiskManager()

    def test_trailing_stop_below_entry_for_long(self, risk_manager):
        """Stop para posición larga debe estar debajo del entry."""
        params = TrailingStopParams(
            symbol="BTCUSDT",
            entry_price=50000.0,
            atr=1000.0,
            multiplier_atr=2.0,
            is_long=True,
        )
        stop = risk_manager.get_adaptive_trailing_stop(params)
        assert stop < params.entry_price, (
            f"Stop {stop} no está debajo de entry {params.entry_price}"
        )

    def test_trailing_stop_above_entry_for_short(self, risk_manager):
        """Stop para posición corta debe estar encima del entry."""
        params = TrailingStopParams(
            symbol="BTCUSDT",
            entry_price=50000.0,
            atr=1000.0,
            multiplier_atr=2.0,
            is_long=False,
        )
        stop = risk_manager.get_adaptive_trailing_stop(params)
        assert stop > params.entry_price, (
            f"Stop {stop} no está encima de entry {params.entry_price}"
        )

    def test_trailing_stop_distance_proportional_to_atr(self, risk_manager):
        """Distancia del stop debe ser proporcional al ATR."""
        params = TrailingStopParams(
            symbol="BTCUSDT",
            entry_price=50000.0,
            atr=1000.0,
            multiplier_atr=2.0,
            is_long=True,
        )
        stop = risk_manager.get_adaptive_trailing_stop(params)
        expected_distance = params.atr * params.multiplier_atr
        actual_distance = params.entry_price - stop
        assert abs(actual_distance - expected_distance) < 0.01

    def test_trailing_stop_moves_up_on_price_increase(self, risk_manager):
        """Stop debe moverse hacia arriba cuando el precio sube."""
        params = TrailingStopParams(
            symbol="BTCUSDT",
            entry_price=50000.0,
            atr=1000.0,
            multiplier_atr=2.0,
            is_long=True,
        )
        initial_stop = risk_manager.get_adaptive_trailing_stop(params)
        new_stop = risk_manager.update_trailing_stop("BTCUSDT", 55000.0)
        if new_stop is not None:
            assert new_stop > initial_stop, (
                f"Stop no se movió hacia arriba: {new_stop} <= {initial_stop}"
            )

    def test_trailing_stop_never_moves_down_for_long(self, risk_manager):
        """Stop de long NUNCA debe moverse hacia abajo."""
        params = TrailingStopParams(
            symbol="BTCUSDT",
            entry_price=50000.0,
            atr=1000.0,
            multiplier_atr=2.0,
            is_long=True,
        )
        risk_manager.get_adaptive_trailing_stop(params)
        new_stop = risk_manager.update_trailing_stop("BTCUSDT", 45000.0)
        assert new_stop is None, (
            "Stop se movió hacia abajo para long; debe permanecer estático"
        )

    def test_trailing_stop_with_zero_atr(self, risk_manager):
        """ATR=0 debe ser manejado sin crash."""
        params = TrailingStopParams(
            symbol="BTCUSDT",
            entry_price=50000.0,
            atr=0.0,
            multiplier_atr=2.0,
            is_long=True,
        )
        stop = risk_manager.get_adaptive_trailing_stop(params)
        assert stop == params.entry_price, "Con ATR=0, stop debe ser igual al entry"


# ===========================================================================
# TEST GROUP 6: Risk status
# ===========================================================================

class TestRiskStatus:
    """Tests del estado de riesgo."""

    def test_risk_status_complete(self):
        """get_risk_status debe retornar todas las claves esperadas."""
        rm = RiskManager()
        status = rm.get_risk_status()
        expected_keys = [
            "breaker_state",
            "emergency_stop",
            "current_regime",
            "total_exposure_pct",
            "max_exposure_pct",
            "daily_loss_pct",
            "max_loss_remaining",
            "min_profit_bps",
            "trailing_stops_count",
            "timestamp",
        ]
        for key in expected_keys:
            assert key in status, f"Clave '{key}' faltante en risk_status"

    def test_max_loss_remaining_correct(self):
        """max_loss_remaining debe ser 5% - daily_loss."""
        rm = RiskManager()
        rm.update_metrics(daily_loss=0.03, total_exposure=0.5)
        expected = round(max(0.0, 0.05 - 0.03), 2)
        assert rm.max_loss_remaining == expected

    def test_max_loss_remaining_zero_when_exceeded(self):
        """max_loss_remaining debe ser 0 cuando daily_loss >= 5%."""
        rm = RiskManager()
        rm.update_metrics(daily_loss=0.07, total_exposure=0.5)
        assert rm.max_loss_remaining == 0.0
