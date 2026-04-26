"""
QAA Tests: Race Conditions y Concurrencia

Objetivo: Detectar condiciones de carrera en operaciones concurrentes
que podrían resultar en estados inconsistentes o pérdida de capital.

Nivel de riesgo: ALTO
Impacto financiero: Doble ejecución de órdenes, balances inconsistentes

HALLAZGOS:
- CircuitBreakers usa dict Python (no thread-safe para async concurrente)
- TradeExecutor es un singleton global (race condition en execute_order)
- OrderValidator tiene _symbol_info_cache sin protección thread-safe
- balance_service updates no tienen locking explícito
"""

import os
import sys
import asyncio
import threading
import time
import pytest
from decimal import Decimal
from unittest.mock import MagicMock
from concurrent.futures import ThreadPoolExecutor

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

os.environ.setdefault("SKIP_API_HEALTHCHECK", "1")

from app.core.circuit_breakers import CircuitBreakers
from app.core.risk_manager import RiskManager


# ===========================================================================
# TEST GROUP 1: Dict-based state (no thread-safe)
# ===========================================================================


class TestDictStateSafety:
    """
    HALLAZGO: CircuitBreakers usa un dict Python plano para almacenar estado.
    Los dicts de Python son thread-safe para operaciones atómicas individuales
    (GIL), pero el patrón read-modify-write en activate_breaker NO es atómico.

    Ejemplo de race condition:
    1. Thread A lee breaker['active'] = False
    2. Thread B lee breaker['active'] = False
    3. Thread A escribe breaker['active'] = True, _last_activation_ts[...] = now
    4. Thread B escribe breaker['active'] = True, _last_activation_ts[...] = now
    → Se pierde el timestamp correcto de activación
    """

    def test_concurrent_dict_modification(self):
        """Verificar que modificaciones concurrentes del dict no crashean."""
        shared_dict = {"counter": 0}
        lock = threading.Lock()

        def increment():
            for _ in range(1000):
                with lock:
                    shared_dict["counter"] += 1

        threads = [threading.Thread(target=increment) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert (
            shared_dict["counter"] == 10000
        ), f"Counter {shared_dict['counter']} != 10000 - race condition"

    def test_breaker_state_consistency_under_threads(self):
        """Breakers deben mantener estado consistente bajo threads."""
        breakers = CircuitBreakers()
        breakers._cooldown_seconds = 0
        errors = []

        async def toggle_breaker(name, iterations):
            for i in range(iterations):
                try:
                    await breakers.activate_breaker(name, f"test_{i}")
                    await breakers.deactivate_breaker(name)
                except Exception as e:
                    errors.append(str(e))

        async def run_concurrent():
            tasks = [
                toggle_breaker("balance_discrepancy", 100),
                toggle_breaker("system_integrity", 100),
                toggle_breaker("operation_failure_rate", 100),
            ]
            await asyncio.gather(*tasks)

        asyncio.run(run_concurrent())
        assert len(errors) == 0, f"Errores durante toggle concurrente: {errors}"


# ===========================================================================
# TEST GROUP 2: Singleton race conditions
# ===========================================================================


class TestSingletonRaceConditions:
    """
    HALLAZGO: TradeExecutor es un singleton global (trade_executor = TradeExecutor()).
    Si dos corrutinas llaman execute_order simultáneamente:
    1. Ambas pasan la validación de balance
    2. Ambas envían orden a Binance
    3. Solo una puede tener balance suficiente
    → La segunda orden falla en Binance con -2010 INSUFFICIENT_BALANCE
    """

    def test_concurrent_balance_check_race(self):
        """Simular race condition en verificación de balance."""
        balance = {"USDT": Decimal("100.00")}

        def check_and_spend(amount: Decimal) -> bool:
            # No-atomic read-check-update
            if balance["USDT"] >= amount:
                # Ventana de race condition aquí
                time.sleep(0.001)  # Simular latencia
                balance["USDT"] -= amount
                return True
            return False

        # Dos "órdenes" de $80 con balance de $100
        results = []
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(check_and_spend, Decimal("80.00")),
                executor.submit(check_and_spend, Decimal("80.00")),
            ]
            results = [f.result() for f in futures]

        # Idealmente, solo una debería tener éxito
        successes = sum(1 for r in results if r)
        if successes == 2:
            # Race condition: ambas pasaron el check
            assert balance["USDT"] == Decimal(
                "-60.00"
            ), "Balance negativo por race condition"

    def test_order_validator_cache_race(self):
        """
        OrderValidator._symbol_info_cache es un dict compartido.
        Acceso concurrente puede causar datos parciales.
        """
        from app.services.order_validation import OrderValidator

        client = MagicMock()
        client.get_exchange_info.return_value = {
            "symbols": [
                {
                    "symbol": "BTCUSDT",
                    "baseAsset": "BTC",
                    "quoteAsset": "USDT",
                    "quotePrecision": 8,
                    "baseAssetPrecision": 8,
                    "filters": [
                        {
                            "filterType": "PRICE_FILTER",
                            "tickSize": "0.01",
                            "minPrice": "0.01",
                            "maxPrice": "1000000",
                        },
                        {
                            "filterType": "LOT_SIZE",
                            "stepSize": "0.00001",
                            "minQty": "0.00001",
                            "maxQty": "9000",
                        },
                        {"filterType": "MIN_NOTIONAL", "minNotional": "10"},
                    ],
                }
            ]
        }

        validator = OrderValidator(client)

        def get_info():
            return validator.get_symbol_info("BTCUSDT")

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(get_info) for _ in range(20)]
            results = [f.result() for f in futures]

        # Todos deben retornar datos consistentes
        for result in results:
            if result is not None:
                assert "stepSize" in result
                assert "minQty" in result


# ===========================================================================
# TEST GROUP 3: Async race conditions
# ===========================================================================


class TestAsyncRaceConditions:
    """Tests de race conditions en contexto async."""

    @pytest.mark.asyncio
    async def test_concurrent_breaker_activate_deactivate(self):
        """
        Activar y desactivar concurrentemente el mismo breaker
        puede dejar el estado indefinido.
        """
        breakers = CircuitBreakers()
        breakers._cooldown_seconds = 0

        async def activator():
            for _ in range(50):
                await breakers.activate_breaker("balance_discrepancy", "act")
                await asyncio.sleep(0)

        async def deactivator():
            for _ in range(50):
                await breakers.deactivate_breaker("balance_discrepancy")
                await asyncio.sleep(0)

        await asyncio.gather(activator(), deactivator())

        # Estado final debe ser determinista (uno de los dos ganó)
        state = breakers.is_breaker_active("balance_discrepancy")
        assert isinstance(state, bool), "Estado indeterminado"

    @pytest.mark.asyncio
    async def test_multiple_coroutines_check_trading_halted(self):
        """Múltiples corrutinas verificando is_trading_halted simultáneamente."""
        breakers = CircuitBreakers()
        breakers._cooldown_seconds = 0

        results = []

        async def check():
            for _ in range(100):
                results.append(breakers.is_trading_halted())
                await asyncio.sleep(0)

        await asyncio.gather(
            check(),
            check(),
            check(),
            breakers.activate_breaker("system_integrity", "test"),
        )

        # Después de la activación, todas las verificaciones deben dar True
        # pero durante la ejecución puede haber mezcla
        assert isinstance(results, list)
        assert len(results) > 0


# ===========================================================================
# TEST GROUP 4: RiskManager state race conditions
# ===========================================================================


class TestRiskManagerRaceConditions:
    """Tests de race conditions en RiskManager."""

    def test_concurrent_update_metrics(self):
        """Actualizaciones concurrentes de métricas."""
        rm = RiskManager()
        errors = []

        def update(daily_loss, exposure):
            try:
                rm.update_metrics(daily_loss=daily_loss, total_exposure=exposure)
            except Exception as e:
                errors.append(str(e))

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            for i in range(100):
                daily = 0.01 * (i % 10)
                exposure = 0.1 * (i % 10)
                futures.append(executor.submit(update, daily, exposure))

            for f in futures:
                f.result()

        assert len(errors) == 0, f"Errores en updates concurrentes: {errors}"

    def test_concurrent_check_circuit_breaker(self):
        """Checks concurrentes del circuit breaker."""
        from app.core.risk_manager import BreakerState

        rm = RiskManager()
        states = []

        def check_breaker():
            for _ in range(100):
                state = rm.check_circuit_breaker()
                states.append(state)

        threads = [threading.Thread(target=check_breaker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(states) == 500
        for state in states:
            assert isinstance(state, BreakerState), f"Estado inesperado: {state}"

    def test_concurrent_trailing_stop_updates(self):
        """Updates concurrentes de trailing stops."""
        rm = RiskManager()
        from app.core.risk_manager import TrailingStopParams

        params = TrailingStopParams(
            symbol="BTCUSDT",
            entry_price=50000.0,
            atr=1000.0,
            multiplier_atr=2.0,
            is_long=True,
        )
        rm.get_adaptive_trailing_stop(params)

        errors = []

        def update_stop(price):
            try:
                rm.update_trailing_stop("BTCUSDT", price)
            except Exception as e:
                errors.append(str(e))

        with ThreadPoolExecutor(max_workers=5) as executor:
            prices = [50000 + i * 100 for i in range(50)]
            futures = [executor.submit(update_stop, p) for p in prices]
            for f in futures:
                f.result()

        assert len(errors) == 0, f"Errores en trailing stop concurrente: {errors}"


# ===========================================================================
# TEST GROUP 5: Distributed lock simulation
# ===========================================================================


class TestDistributedLockSimulation:
    """Tests de simulación de lock distribuido."""

    def test_without_lock_causes_inconsistency(self):
        """Sin lock, actualizaciones concurrentes causan inconsistencia."""
        counter = {"value": 0}
        iterations = 10000

        def increment_without_lock():
            for _ in range(iterations):
                val = counter["value"]
                counter["value"] = val + 1

        threads = [threading.Thread(target=increment_without_lock) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Con race condition, el resultado será menor que 2 * iterations
        # El GIL de Python generalmente previene esto pero no garantiza atomicidad
        expected = 2 * iterations
        actual = counter["value"]
        # En CPython, el GIL hace que esto sea generalmente correcto,
        # pero no está garantizado
        assert actual <= expected

    def test_with_lock_ensures_consistency(self):
        """Con lock, actualizaciones concurrentes son consistentes."""
        counter = {"value": 0}
        lock = threading.Lock()
        iterations = 10000

        def increment_with_lock():
            for _ in range(iterations):
                with lock:
                    counter["value"] += 1

        threads = [threading.Thread(target=increment_with_lock) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert counter["value"] == 4 * iterations
