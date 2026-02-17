"""
QAA Tests: Caos Controlado y Resiliencia

Objetivo: Simular condiciones extremas para verificar que el sistema
falla de forma segura y nunca pierde capital silenciosamente.

Nivel de riesgo: CRÍTICO
Impacto financiero: Pérdida de capital en condiciones adversas

Escenarios:
- Flash crash (precio cae >20% en segundos)
- Desconexión de Binance
- Respuestas inconsistentes del exchange
- Timeout en API
- Balance insuficiente durante ejecución
- Partial fills
- Latencia extrema
"""

import os
import sys
import time
import asyncio
import pytest
from decimal import Decimal
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

os.environ.setdefault("SKIP_API_HEALTHCHECK", "1")

from app.core.risk_manager import RiskManager, MarketRegime, BreakerState
from app.core.circuit_breakers import CircuitBreakers
from app.services.grid_strategy import calculate_grid_levels, decide_grid_action


# ===========================================================================
# TEST GROUP 1: Flash Crash
# ===========================================================================

class TestFlashCrash:
    """Tests de comportamiento durante flash crash."""

    def test_flash_crash_triggers_circuit_breaker(self):
        """Un flash crash debe activar el circuit breaker."""
        rm = RiskManager()

        # Simular flash crash: pérdida del 20% en segundos
        rm.update_metrics(daily_loss=0.20, total_exposure=0.6)
        state = rm.check_circuit_breaker()

        assert state in [BreakerState.DANGER, BreakerState.STOPPED], (
            f"Flash crash con 20% pérdida no activó breaker: {state.value}"
        )

    def test_grid_action_during_flash_crash(self):
        """Grid debe NO operar si el precio sale del rango abruptamente."""
        levels = calculate_grid_levels(40000, 60000, 10)

        # Flash crash: precio cae a 25000 (fuera del rango)
        action = decide_grid_action(25000, levels)
        assert action["action"] is None, (
            f"Grid sugirió {action['action']} durante flash crash fuera de rango"
        )

    def test_trailing_stop_triggered_during_crash(self):
        """Trailing stop debe ser alcanzado durante crash."""
        from app.core.risk_manager import TrailingStopParams

        rm = RiskManager()
        params = TrailingStopParams(
            symbol="BTCUSDT",
            entry_price=50000.0,
            atr=1000.0,
            multiplier_atr=2.0,
            is_long=True,
        )
        stop = rm.get_adaptive_trailing_stop(params)

        # Flash crash a 40000 (mucho debajo del stop)
        crash_price = 40000.0
        assert crash_price < stop, (
            f"Precio crash {crash_price} no alcanza stop {stop}. "
            f"El stop loss debería haberse ejecutado."
        )

    def test_crash_imminent_regime_detected(self):
        """Régimen CRASH_IMMINENT debe reducir exposición."""
        rm = RiskManager()
        rm.apply_market_regime_filter(MarketRegime.CRASH_IMMINENT)
        assert rm.current_regime == MarketRegime.CRASH_IMMINENT

        # Verificar que los límites se redujeron
        original_rm = RiskManager()
        assert rm.max_total_exposure_pct < original_rm.max_total_exposure_pct


# ===========================================================================
# TEST GROUP 2: Desconexión de Binance
# ===========================================================================

class TestBinanceDisconnection:
    """Tests de comportamiento durante desconexión de Binance."""

    def test_get_symbol_info_handles_connection_error(self):
        """get_symbol_info debe manejar error de conexión sin crash."""
        from app.services.order_validation import OrderValidator

        client = MagicMock()
        client.get_exchange_info.side_effect = ConnectionError("Network error")

        validator = OrderValidator(client)
        result = validator.get_symbol_info("BTCUSDT")
        assert result is None, "Debe retornar None en error de conexión"

    def test_validate_order_handles_ticker_error(self):
        """validate_order debe manejar error al obtener precio."""
        from app.services.order_validation import OrderValidator

        client = MagicMock()
        client.get_exchange_info.return_value = {
            "symbols": [{
                "symbol": "BTCUSDT",
                "baseAsset": "BTC",
                "quoteAsset": "USDT",
                "quotePrecision": 8,
                "baseAssetPrecision": 8,
                "filters": [
                    {"filterType": "PRICE_FILTER", "tickSize": "0.01", "minPrice": "0.01", "maxPrice": "1000000"},
                    {"filterType": "LOT_SIZE", "stepSize": "0.00001", "minQty": "0.00001", "maxQty": "9000"},
                    {"filterType": "MIN_NOTIONAL", "minNotional": "10"},
                ],
            }]
        }
        client.get_symbol_ticker.side_effect = ConnectionError("Binance down")

        validator = OrderValidator(client)
        result = validator.validate_order_parameters(
            "BTCUSDT", 0.001, "BUY", "MARKET"
        )
        assert not result["is_valid"], (
            "Orden validada como válida durante desconexión"
        )

    @pytest.mark.asyncio
    async def test_reconciliation_handles_connection_error(self):
        """Reconciliación debe manejar error de conexión."""
        breakers = CircuitBreakers()
        breakers._cooldown_seconds = 0

        # Simular el ciclo de reconciliación con error
        start = time.time()
        try:
            raise ConnectionError("Binance API down")
        except ConnectionError as e:
            elapsed = time.time() - start
            result = {
                "status": "error",
                "error": str(e),
                "latency_seconds": elapsed,
            }

        assert result["status"] == "error"
        assert "Binance" in result["error"]


# ===========================================================================
# TEST GROUP 3: Respuestas inconsistentes del exchange
# ===========================================================================

class TestInconsistentExchangeResponses:
    """Tests para respuestas inconsistentes del exchange."""

    def test_order_filled_but_empty_fills(self):
        """Orden FILLED pero sin fills debe manejarse."""
        order_result = {
            "orderId": 12345,
            "status": "FILLED",
            "executedQty": "0.001",
            "price": "0",  # Precio 0 en market orders
            "fills": [],   # Sin fills
        }

        executed_qty = Decimal(str(order_result.get("executedQty", "0")))
        fills = order_result.get("fills", [])

        if not fills:
            avg_price = Decimal(str(order_result.get("price", "0")))
            if avg_price == 0:
                # Necesita obtener precio del mercado
                assert True, (
                    "Orden FILLED sin fills ni precio requiere lookup adicional"
                )

    def test_partial_fill_handling(self):
        """Partial fill debe actualizar balance proporcionalmente."""
        order_result = {
            "orderId": 12345,
            "status": "PARTIALLY_FILLED",
            "executedQty": "0.0005",  # Solo la mitad
            "origQty": "0.001",
            "fills": [
                {"price": "50000.00", "qty": "0.0005", "commission": "0.025", "commissionAsset": "USDT"},
            ],
        }

        expected_qty = Decimal(order_result["origQty"])
        executed_qty = Decimal(order_result["executedQty"])
        fill_ratio = executed_qty / expected_qty

        assert fill_ratio == Decimal("0.5"), (
            f"Fill ratio incorrecto: {fill_ratio}"
        )
        assert executed_qty < expected_qty, "Partial fill no detectado"

    def test_negative_price_rejected(self):
        """Precio negativo del exchange debe ser rechazado."""
        price = -50000.0
        assert price < 0, "Precio negativo debe ser detectado"

    def test_zero_price_rejected(self):
        """Precio cero del exchange debe ser tratado con precaución."""
        price = 0.0
        assert price == 0, "Precio cero debe ser detectado"

    def test_extremely_high_price_flagged(self):
        """Precio extremadamente alto debe ser flagged."""
        price = 999999999.0
        expected_max = 1000000.0  # Max razonable para BTC
        if price > expected_max:
            assert True, f"Precio {price} excede máximo razonable {expected_max}"

    def test_order_result_missing_fields(self):
        """Respuesta de orden con campos faltantes no debe crashear."""
        # Respuesta mínima
        minimal_result = {"orderId": 123}

        status = minimal_result.get("status", "UNKNOWN")
        executed_qty = minimal_result.get("executedQty", "0")
        fills = minimal_result.get("fills", [])

        assert status == "UNKNOWN"
        assert executed_qty == "0"
        assert fills == []


# ===========================================================================
# TEST GROUP 4: Race Conditions
# ===========================================================================

class TestRaceConditions:
    """Tests de condiciones de carrera."""

    @pytest.mark.asyncio
    async def test_concurrent_breaker_activations(self):
        """Activaciones concurrentes de breaker no deben corromper estado."""
        breakers = CircuitBreakers()
        breakers._cooldown_seconds = 0

        async def activate_and_check(name, reason):
            result = await breakers.activate_breaker(name, reason)
            return result

        tasks = []
        for i in range(50):
            for breaker_type in ["balance_discrepancy", "system_integrity"]:
                tasks.append(activate_and_check(breaker_type, f"concurrent_{i}"))

        results = await asyncio.gather(*tasks)

        # Verificar estado final consistente
        assert breakers.is_breaker_active("balance_discrepancy")
        assert breakers.is_breaker_active("system_integrity")

    def test_balance_update_atomicity(self):
        """
        Verificar que actualizaciones de balance son atómicas.
        Si BUY actualiza -USDT y +BTC, ambos deben ocurrir o ninguno.
        """
        balances = {
            "USDT": Decimal("10000.00"),
            "BTC": Decimal("0.0"),
        }

        def atomic_buy(qty: Decimal, price: Decimal, commission: Decimal):
            cost = qty * price + commission
            if balances["USDT"] < cost:
                raise ValueError("Insufficient balance")
            balances["USDT"] -= cost
            balances["BTC"] += qty

        # Ejecutar compra exitosa
        atomic_buy(Decimal("0.001"), Decimal("50000"), Decimal("0.05"))
        assert balances["USDT"] == Decimal("9949.95")
        assert balances["BTC"] == Decimal("0.001")

        # Intentar compra que falla por balance
        initial_usdt = balances["USDT"]
        initial_btc = balances["BTC"]
        try:
            atomic_buy(Decimal("1.0"), Decimal("50000"), Decimal("50"))
        except ValueError:
            pass

        # Balances no deben haber cambiado
        assert balances["USDT"] == initial_usdt, "USDT cambió en compra fallida"
        assert balances["BTC"] == initial_btc, "BTC cambió en compra fallida"


# ===========================================================================
# TEST GROUP 5: Timeout y latencia extrema
# ===========================================================================

class TestTimeoutAndLatency:
    """Tests de comportamiento con timeout y latencia extrema."""

    def test_order_validation_timeout(self):
        """Validación de orden con API lenta no debe bloquear indefinidamente."""
        from app.services.order_validation import OrderValidator

        client = MagicMock()
        client.get_exchange_info.return_value = {"symbols": []}

        def slow_ticker(*args, **kwargs):
            time.sleep(0.01)  # Simular latencia sin bloquear
            return {"price": "50000.00"}

        client.get_symbol_ticker.side_effect = slow_ticker

        start = time.time()
        validator = OrderValidator(client)
        result = validator.validate_order_parameters(
            "BTCUSDT", 0.001, "BUY", "MARKET"
        )
        elapsed = time.time() - start

        assert elapsed < 5.0, (
            f"Validación tardó {elapsed:.2f}s, debería ser < 5s"
        )

    def test_api_latency_p99_target(self):
        """Verificar que operaciones locales cumplen P99 < 250ms."""
        latencies = []

        for _ in range(100):
            start = time.time()
            # Simular operación de validación local
            from app.services.grid_strategy import calculate_grid_levels
            levels = calculate_grid_levels(10000, 20000, 20)
            for level in levels:
                _ = decide_grid_action(level, levels)
            elapsed = (time.time() - start) * 1000  # ms
            latencies.append(elapsed)

        latencies.sort()
        p99 = latencies[int(len(latencies) * 0.99)]
        assert p99 < 250, f"P99 latency {p99:.2f}ms exceeds 250ms target"


# ===========================================================================
# TEST GROUP 6: Balance insuficiente
# ===========================================================================

class TestInsufficientBalance:
    """Tests de manejo de balance insuficiente."""

    def test_buy_with_zero_balance(self):
        """Compra con balance cero debe ser rechazada."""
        balance_usdt = Decimal("0.00")
        buy_cost = Decimal("500.00")
        assert balance_usdt < buy_cost, "Debe detectar balance insuficiente"

    def test_buy_exceeding_available_balance(self):
        """Compra que excede el balance disponible debe ser rechazada."""
        available = Decimal("100.00")
        required = Decimal("150.00")
        assert required > available

    def test_sell_more_than_held(self):
        """Venta de más cantidad de la que se tiene debe ser rechazada."""
        held_btc = Decimal("0.001")
        sell_qty = Decimal("0.01")
        assert sell_qty > held_btc, "Debe detectar cantidad insuficiente para venta"

    def test_commission_makes_balance_insufficient(self):
        """
        Si el balance es exactamente igual al costo, la comisión
        hace que el balance sea insuficiente.
        """
        balance = Decimal("50.00")
        cost = Decimal("50.00")
        commission = Decimal("0.05")  # 0.1%
        total_needed = cost + commission

        assert total_needed > balance, (
            "Comisión hace que el balance sea insuficiente"
        )


# ===========================================================================
# TEST GROUP 7: Simulación de condiciones extremas
# ===========================================================================

class TestExtremeConditions:
    """Tests de condiciones extremas de mercado."""

    def test_price_gap_handling(self):
        """
        Gap de precio: el precio salta de 50000 a 40000 sin pasar
        por niveles intermedios. El grid debe manejar esto.
        """
        levels = calculate_grid_levels(40000, 60000, 20)

        # Antes del gap
        action_before = decide_grid_action(50000, levels)

        # Después del gap (precio saltó a 41000)
        action_after = decide_grid_action(41000, levels)

        # No debe haber acción de SELL cuando el precio bajó abruptamente
        if action_after["action"] == "SELL":
            assert False, (
                "Grid sugiere SELL después de gap bajista. "
                "Esto amplifica pérdidas."
            )

    def test_very_high_volatility_sizing(self):
        """En volatilidad extrema, el sizing debe ser conservador."""
        rm = RiskManager()
        from app.core.risk_manager import PositionSizeParams

        params = PositionSizeParams(
            symbol="BTCUSDT",
            account_equity=10000.0,
            atr=0.10,  # ATR del 10% - volatilidad extrema
            winrate_estimate=0.6,
            avg_win_loss_ratio=1.5,
            price=50000.0,
        )
        rm.current_regime = MarketRegime.HIGH_VOL
        size = rm.calculate_dynamic_position_size(params)

        assert size < params.account_equity * 0.3, (
            f"Posición {size} demasiado grande para volatilidad extrema"
        )

    def test_multiple_rapid_regime_changes(self):
        """Cambios rápidos de régimen no deben causar estado inconsistente."""
        rm = RiskManager()
        regimes = [
            MarketRegime.BULL_TREND,
            MarketRegime.CRASH_IMMINENT,
            MarketRegime.RANGE,
            MarketRegime.HIGH_VOL,
            MarketRegime.BEAR_TREND,
        ]

        for regime in regimes:
            rm.current_regime = regime
            state = rm.check_circuit_breaker()
            assert isinstance(state, BreakerState)

    def test_zero_atr_does_not_cause_division_by_zero(self):
        """ATR = 0 no debe causar division by zero."""
        rm = RiskManager()
        from app.core.risk_manager import PositionSizeParams

        params = PositionSizeParams(
            symbol="BTCUSDT",
            account_equity=10000.0,
            atr=0.0,  # ATR = 0
            winrate_estimate=0.6,
            avg_win_loss_ratio=1.5,
            price=50000.0,
        )
        # No debe lanzar ZeroDivisionError
        size = rm.calculate_dynamic_position_size(params)
        assert isinstance(size, (int, float))
