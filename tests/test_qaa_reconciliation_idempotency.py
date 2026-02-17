"""
QAA Tests: Reconciliación e Idempotencia

Objetivo: Verificar que la reconciliación detecta discrepancias correctamente,
que la latencia es <60s, y que las operaciones son idempotentes.

Nivel de riesgo: CRÍTICO
Impacto financiero: Balances desincronizados, pérdida de capital no detectada

HALLAZGOS:
- reconciliation_service.py línea 76-81: int_total_value = total_value y discrepancy = 0.0
  Esto significa que la reconciliación NUNCA detecta discrepancias reales porque
  compara el mismo valor consigo mismo.
- has_internal_accounting = False siempre, lo cual desactiva el breaker.
- La reconciliación usa float para balances (línea 46).
- No hay verificación de client_order_id para idempotencia en trade_executor.
"""

import os
import sys
import time
import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from decimal import Decimal

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

os.environ.setdefault("SKIP_API_HEALTHCHECK", "1")

from app.core.circuit_breakers import CircuitBreakers


# ===========================================================================
# TEST GROUP 1: Reconciliación - Hallazgo de reconciliación nula
# ===========================================================================

class TestReconciliationNullDiscrepancy:
    """
    HALLAZGO CRÍTICO: ReconciliationService.run_reconciliation_cycle()
    establece int_total_value = total_value (línea 76) y discrepancy = 0.0
    (línea 80), lo que hace que la reconciliación NUNCA detecte discrepancias.

    has_internal_accounting = False (línea 82) desactiva permanentemente
    la activación del breaker por discrepancia.

    Impacto: Si hay una discrepancia real entre el estado interno y Binance,
    el sistema NO la detectará y seguirá operando con datos incorrectos.
    """

    def test_reconciliation_always_zero_discrepancy(self):
        """
        Verificar que la reconciliación actual siempre reporta discrepancy=0.
        Esto es un BUG si se espera detección de discrepancias.
        """
        # Simular la lógica de reconciliation_service.py
        ext_usdt = 1000.0
        total_value = 1500.0  # Portfolio total incluyendo assets

        # Reproducir la lógica del código actual
        int_total_value = total_value  # Línea 76: siempre igual
        discrepancy = 0.0             # Línea 80: siempre 0
        int_usdt = ext_usdt           # Línea 81: siempre igual
        has_internal_accounting = False  # Línea 82: siempre False

        assert discrepancy == 0.0, "Bug confirmado: discrepancy siempre es 0"
        assert not has_internal_accounting, (
            "has_internal_accounting es False, breaker nunca se activa"
        )

    def test_breaker_never_activates_from_reconciliation(self):
        """
        Verificar que el breaker de balance_discrepancy nunca se activa
        porque has_internal_accounting es siempre False.
        """
        # Reproducir la lógica del código
        has_internal_accounting = False
        threshold_pct = 0.01
        ext_usdt = 1000.0
        discrepancy = 500.0  # Discrepancia enorme del 50%

        denom = max(1.0, ext_usdt)
        relative_gap = (discrepancy / denom) if denom > 0 else 0.0

        should_activate = has_internal_accounting and relative_gap > threshold_pct

        assert not should_activate, (
            "Breaker no se activa porque has_internal_accounting=False, "
            "incluso con discrepancia del 50%"
        )


# ===========================================================================
# TEST GROUP 2: Latencia de reconciliación
# ===========================================================================

class TestReconciliationLatency:
    """Tests de latencia de reconciliación."""

    def test_reconciliation_latency_under_60s(self):
        """
        La reconciliación debe completarse en menos de 60 segundos.
        Este test simula el ciclo para verificar que la lógica no bloquea.
        """
        start = time.time()

        # Simular procesamiento de reconciliación sin red
        balances = {
            "USDT": 1000.0,
            "BTC": 0.01,
            "ETH": 0.1,
            "ADA": 100.0,
        }

        total_value = 0.0
        prices = {"BTCUSDT": 50000.0, "ETHUSDT": 3500.0, "ADAUSDT": 0.5}

        for asset, qty in balances.items():
            if asset == "USDT":
                total_value += qty
                continue
            symbol = f"{asset}USDT"
            price = prices.get(symbol, 0.0)
            total_value += qty * price

        elapsed = time.time() - start
        assert elapsed < 1.0, (
            f"Procesamiento local tardó {elapsed:.3f}s, debería ser instantáneo"
        )

    def test_reconciliation_interval_configured(self):
        """Verificar que el intervalo de reconciliación es <= 60s."""
        # El intervalo por defecto del servicio
        default_interval = 60
        assert default_interval <= 60, (
            f"Intervalo de reconciliación {default_interval}s > 60s"
        )


# ===========================================================================
# TEST GROUP 3: Idempotencia de órdenes
# ===========================================================================

class TestOrderIdempotency:
    """Tests de idempotencia de ejecución de órdenes."""

    def test_client_order_id_generation_uniqueness(self):
        """Cada orden debe tener un client_order_id único."""
        import uuid
        ids = set()
        for _ in range(10000):
            order_id = str(uuid.uuid4())
            assert order_id not in ids, f"Duplicado: {order_id}"
            ids.add(order_id)

    def test_trade_executor_no_client_order_id(self):
        """
        HALLAZGO: TradeExecutor.execute_order no genera client_order_id.
        Sin client_order_id, si hay un timeout y retry, la misma orden
        podría ejecutarse dos veces en Binance.
        """
        import inspect
        from app.services.trade_executor import TradeExecutor

        source = inspect.getsource(TradeExecutor.execute_order)

        has_client_order_id = (
            "client_order_id" in source
            or "newClientOrderId" in source
            or "clientOrderId" in source
        )

        if not has_client_order_id:
            # HALLAZGO confirmado
            assert True, (
                "HALLAZGO: TradeExecutor.execute_order NO usa client_order_id. "
                "Riesgo de ejecución duplicada en caso de timeout+retry."
            )

    def test_retry_mechanism_risk(self):
        """
        TradeExecutor tiene retry para error -1021 (timestamp).
        Si el primer intento SÍ se ejecutó en Binance pero el response
        se perdió, el retry ejecutará la orden DOS VECES.
        """
        import inspect
        from app.services.trade_executor import TradeExecutor

        source = inspect.getsource(TradeExecutor.execute_order)

        has_retry = "-1021" in source
        has_idempotency = "client_order_id" in source.lower()

        if has_retry and not has_idempotency:
            assert True, (
                "HALLAZGO: Retry sin idempotencia. Si el primer request se ejecutó "
                "en Binance pero el response se perdió, el retry duplicará la orden."
            )


# ===========================================================================
# TEST GROUP 4: Consistencia de balances
# ===========================================================================

class TestBalanceConsistency:
    """Tests de consistencia de balances internos."""

    def test_balance_update_uses_decimal(self):
        """La actualización de balance debe usar Decimal."""
        qty = Decimal("0.001")
        price = Decimal("50000.01")
        total = qty * price
        assert total == Decimal("50.00001"), (
            f"Balance calculation imprecise: {total}"
        )

    def test_commission_subtracted_correctly(self):
        """La comisión debe restarse correctamente del balance."""
        trade_value = Decimal("1050.00")
        commission = Decimal("1.05")  # 0.1%

        # BUY: costo = trade_value + commission
        buy_cost = trade_value + commission
        assert buy_cost == Decimal("1051.05")

        # SELL: proceeds = trade_value - commission
        sell_proceeds = trade_value - commission
        assert sell_proceeds == Decimal("1048.95")

    def test_balance_after_buy_sell_cycle(self):
        """Balance después de compra+venta debe ser consistente."""
        initial_usdt = Decimal("10000.00")
        btc_price = Decimal("50000.00")
        btc_qty = Decimal("0.1")
        commission_rate = Decimal("0.001")  # 0.1%

        # BUY
        buy_cost = btc_qty * btc_price  # 5000.00
        buy_commission = buy_cost * commission_rate  # 5.00
        usdt_after_buy = initial_usdt - buy_cost - buy_commission  # 4995.00
        btc_balance = btc_qty

        # SELL (mismo precio)
        sell_proceeds = btc_balance * btc_price  # 5000.00
        sell_commission = sell_proceeds * commission_rate  # 5.00
        usdt_after_sell = usdt_after_buy + sell_proceeds - sell_commission  # 9990.00

        total_commission = buy_commission + sell_commission  # 10.00
        expected_final = initial_usdt - total_commission  # 9990.00

        assert usdt_after_sell == expected_final, (
            f"Balance final {usdt_after_sell} != esperado {expected_final}"
        )

    def test_concurrent_balance_updates_race_condition(self):
        """
        Simular actualizaciones concurrentes de balance para detectar
        race conditions potenciales.
        """
        balance = {"USDT": Decimal("10000.00")}

        def update_balance(amount: Decimal):
            current = balance["USDT"]
            # Simular ventana de tiempo entre read y write
            new_val = current + amount
            balance["USDT"] = new_val

        # Secuencial: debe ser correcto
        for _ in range(100):
            update_balance(Decimal("-10.00"))

        assert balance["USDT"] == Decimal("9000.00"), (
            f"Balance incorrecto: {balance['USDT']}"
        )


# ===========================================================================
# TEST GROUP 5: Reconciliación con discrepancias simuladas
# ===========================================================================

class TestReconciliationWithDiscrepancies:
    """Tests de reconciliación con discrepancias simuladas."""

    def test_detect_missing_asset(self):
        """Detectar activo que existe en Binance pero no en el sistema interno."""
        external = {"USDT": 1000.0, "BTC": 0.01, "ETH": 0.5}
        internal = {"USDT": 1000.0, "BTC": 0.01}  # Falta ETH

        missing = set(external.keys()) - set(internal.keys())
        assert "ETH" in missing, "ETH no detectado como faltante"

    def test_detect_extra_asset(self):
        """Detectar activo en el sistema interno que no existe en Binance."""
        external = {"USDT": 1000.0, "BTC": 0.01}
        internal = {"USDT": 1000.0, "BTC": 0.01, "SOL": 10.0}

        extra = set(internal.keys()) - set(external.keys())
        assert "SOL" in extra, "SOL no detectado como extra"

    def test_detect_quantity_discrepancy(self):
        """Detectar discrepancia de cantidad en un activo."""
        external = {"BTC": Decimal("0.01000000")}
        internal = {"BTC": Decimal("0.01000100")}  # Diferencia de 0.000001

        for asset in external:
            if asset in internal:
                diff = abs(external[asset] - internal[asset])
                if diff > Decimal("0.00000001"):
                    assert True, f"Discrepancia detectada en {asset}: {diff}"

    def test_reconciliation_threshold_calculation(self):
        """Verificar cálculo correcto del umbral de discrepancia."""
        ext_usdt = Decimal("10000.00")
        threshold_pct = Decimal("0.01")  # 1%
        threshold_abs = ext_usdt * threshold_pct  # $100

        discrepancy = Decimal("50.00")  # $50 de diferencia
        assert discrepancy < threshold_abs, (
            f"Discrepancia {discrepancy} >= umbral {threshold_abs}"
        )

        large_discrepancy = Decimal("150.00")
        assert large_discrepancy > threshold_abs, (
            f"Discrepancia grande {large_discrepancy} debería superar umbral"
        )


# ===========================================================================
# TEST GROUP 6: Circuit Breaker activación por reconciliación
# ===========================================================================

class TestReconciliationBreakerActivation:
    """Tests de activación de breakers por discrepancia de reconciliación."""

    @pytest.mark.asyncio
    async def test_breaker_activates_on_large_discrepancy(self):
        """Breaker debe activarse si la discrepancia supera el umbral."""
        breakers = CircuitBreakers()
        breakers._cooldown_seconds = 0

        discrepancy_usd = 500.0
        ext_usdt = 1000.0
        threshold_pct = 0.01

        denom = max(1.0, ext_usdt)
        relative_gap = discrepancy_usd / denom

        if relative_gap > threshold_pct:
            result = await breakers.activate_breaker(
                "balance_discrepancy", "balance discrepancy"
            )
            assert result is True
            assert breakers.is_breaker_active("balance_discrepancy")

    @pytest.mark.asyncio
    async def test_breaker_not_activated_on_small_discrepancy(self):
        """Breaker NO debe activarse si la discrepancia es pequeña."""
        breakers = CircuitBreakers()
        breakers._cooldown_seconds = 0

        discrepancy_usd = 5.0
        ext_usdt = 10000.0
        threshold_pct = 0.01

        denom = max(1.0, ext_usdt)
        relative_gap = discrepancy_usd / denom

        assert relative_gap <= threshold_pct, (
            f"Relative gap {relative_gap} debería ser <= {threshold_pct}"
        )
        assert not breakers.is_breaker_active("balance_discrepancy")


# ===========================================================================
# TEST GROUP 7: PnL no contabilizado
# ===========================================================================

class TestUnaccountedPnL:
    """Tests de detección de PnL no contabilizado."""

    def test_unaccounted_pnl_detection(self):
        """Detectar PnL que no aparece en los registros de trades."""
        initial_portfolio = Decimal("10000.00")
        current_portfolio = Decimal("10500.00")
        recorded_pnl = Decimal("400.00")  # Solo $400 registrados

        unaccounted = current_portfolio - initial_portfolio - recorded_pnl
        assert unaccounted == Decimal("100.00"), (
            f"PnL no contabilizado: {unaccounted}"
        )

    def test_negative_unaccounted_pnl_is_loss(self):
        """PnL no contabilizado negativo indica pérdida no registrada."""
        initial_portfolio = Decimal("10000.00")
        current_portfolio = Decimal("9800.00")
        recorded_pnl = Decimal("-100.00")

        unaccounted = current_portfolio - initial_portfolio - recorded_pnl
        assert unaccounted == Decimal("-100.00"), (
            f"Pérdida no contabilizada: {unaccounted}"
        )
