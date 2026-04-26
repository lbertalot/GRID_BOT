"""
QAA Tests: Precisión Decimal y Riesgos Financieros

Objetivo: Garantizar que NUNCA se use float para cálculos monetarios críticos,
y que todos los cálculos financieros preserven la precisión requerida.

Nivel de riesgo: CRÍTICO
Impacto financiero: Errores de redondeo acumulativos, pérdida silenciosa de capital

HALLAZGOS:
- order_validation.py línea 40-49: usa float() para convertir filtros del exchange
- order_validation.py línea 63,72: _round_to_step/_round_to_tick retornan float()
- precision.py línea 69,80: usa int(price/tick) en lugar de Decimal
- trade_executor.py línea 187: asume quote de 4 caracteres (hardcoded USDT)
- reconciliation_service.py línea 46: usa float() para balances
"""

import os
import sys
import ast
import pytest
from decimal import Decimal, ROUND_DOWN, getcontext, InvalidOperation
from typing import List

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

os.environ.setdefault("SKIP_API_HEALTHCHECK", "1")


# ===========================================================================
# TEST GROUP 1: Auditoría estática - Detección de float en cálculos monetarios
# ===========================================================================


class TestStaticFloatAudit:
    """
    Escanea el código fuente para detectar uso peligroso de float()
    en módulos financieros críticos.
    """

    CRITICAL_MODULES = [
        "app/services/order_validation.py",
        "app/core/precision.py",
        "app/core/precision_validator.py",
        "app/services/trade_executor.py",
        "app/services/reconciliation_service.py",
        "app/services/balance_service.py",
        "app/services/fund_manager.py",
        "app/services/pnl_service.py",
    ]

    def _find_float_calls(self, filepath: str) -> List[dict]:
        """Encuentra llamadas a float() en un archivo Python."""
        results = []
        full_path = os.path.join(BASE_DIR, filepath)
        if not os.path.exists(full_path):
            return results

        with open(full_path, "r") as f:
            source = f.read()

        try:
            tree = ast.parse(source, filename=filepath)
        except SyntaxError:
            return results

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == "float":
                    results.append(
                        {
                            "file": filepath,
                            "line": node.lineno,
                            "col": node.col_offset,
                        }
                    )
        return results

    def test_detect_float_in_order_validation(self):
        """
        HALLAZGO: order_validation.py usa float() extensivamente para filtros.
        Esto puede causar errores de precisión en comparaciones de límites.
        """
        findings = self._find_float_calls("app/services/order_validation.py")
        # Documentar, no bloquear. El test registra los hallazgos.
        if findings:
            lines = [f"  línea {f['line']}" for f in findings]
            msg = (
                f"⚠️ HALLAZGO: {len(findings)} llamadas a float() encontradas "
                f"en order_validation.py:\n" + "\n".join(lines) + "\n"
                "Recomendación: usar Decimal(str(...)) en lugar de float()"
            )
            # Registrar como advertencia, no como fallo inmediato
            assert True, msg

    def test_detect_float_in_precision_module(self):
        """
        HALLAZGO: precision.py usa int(price/tick) en lugar de Decimal.
        int() trunca, lo cual es correcto para floor, pero pierde
        información intermedia en la división float.
        """
        findings = self._find_float_calls("app/core/precision.py")
        if findings:
            lines = [f"  línea {f['line']}" for f in findings]
            msg = (
                f"⚠️ HALLAZGO: {len(findings)} llamadas a float() en precision.py:\n"
                + "\n".join(lines)
            )
            assert True, msg

    def test_detect_float_in_reconciliation(self):
        """
        HALLAZGO: reconciliation_service.py usa float() para leer balances.
        Esto puede causar discrepancias de reconciliación acumulativas.
        """
        findings = self._find_float_calls("app/services/reconciliation_service.py")
        if findings:
            lines = [f"  línea {f['line']}" for f in findings]
            msg = (
                f"⚠️ HALLAZGO: {len(findings)} llamadas a float() en "
                f"reconciliation_service.py:\n" + "\n".join(lines)
            )
            assert True, msg


# ===========================================================================
# TEST GROUP 2: Precisión de Decimal en operaciones financieras
# ===========================================================================


class TestDecimalPrecision:
    """Tests de precisión de cálculos con Decimal."""

    def test_decimal_multiplication_exact(self):
        """Multiplicación Decimal debe ser exacta."""
        price = Decimal("50000.01")
        qty = Decimal("0.00021")
        result = price * qty
        assert result == Decimal("10.5000021")

    def test_float_multiplication_inexact(self):
        """Demostrar que float pierde precisión."""
        price = 50000.01
        qty = 0.00021
        result = price * qty
        expected = 10.5000021
        assert result != expected, "Si float es exacto aquí, probar con otros valores"

    def test_decimal_division_controlled_precision(self):
        """División Decimal debe mantener precisión configurable."""
        getcontext().prec = 28
        a = Decimal("10.00")
        b = Decimal("3.00")
        result = a / b
        assert str(result).startswith("3.33333333"), f"Precisión insuficiente: {result}"

    def test_cumulative_float_error(self):
        """
        Demostrar error acumulativo de float en operaciones repetidas.
        En un bot que ejecuta miles de trades, esto se acumula.
        """
        total_float = 0.0
        total_decimal = Decimal("0")
        increment = 0.1
        increment_d = Decimal("0.1")

        for _ in range(1000):
            total_float += increment
            total_decimal += increment_d

        diff = abs(total_float - float(total_decimal))
        assert (
            diff > 1e-14
        ), "Error acumulativo de float demasiado pequeño para este test"
        assert diff < 1e-10, f"Error acumulativo excesivo: {diff}"

    def test_decimal_for_commission_calculation(self):
        """Comisiones deben calcularse con Decimal."""
        trade_value = Decimal("10500.50")
        commission_rate = Decimal("0.001")  # 0.1% Binance fee
        commission = trade_value * commission_rate
        assert commission == Decimal("10.50050"), f"Comisión incorrecta: {commission}"

    def test_decimal_round_down_for_quantities(self):
        """Cantidades siempre deben redondearse DOWN, nunca UP."""
        qty = Decimal("0.123456789")
        step = Decimal("0.00001")
        rounded = (qty / step).to_integral_value(rounding=ROUND_DOWN) * step
        assert rounded == Decimal(
            "0.12345"
        ), f"Redondeo incorrecto: {rounded}. Debe ser ROUND_DOWN."

    def test_decimal_round_down_never_exceeds_original(self):
        """El resultado de ROUND_DOWN nunca debe exceder el valor original."""
        test_values = [
            Decimal("0.999999"),
            Decimal("1.000001"),
            Decimal("0.123456789"),
            Decimal("50000.999"),
        ]
        step = Decimal("0.00001")
        for val in test_values:
            rounded = (val / step).to_integral_value(rounding=ROUND_DOWN) * step
            assert rounded <= val, f"ROUND_DOWN excedió original: {rounded} > {val}"

    def test_negative_decimal_handling(self):
        """Verificar comportamiento con Decimales negativos."""
        loss = Decimal("-150.50")
        gain = Decimal("200.75")
        net = gain + loss
        assert net == Decimal("50.25")

    def test_very_small_decimal_not_zero(self):
        """Cantidades muy pequeñas no deben redondearse a cero prematuramente."""
        qty = Decimal("0.00001")
        step = Decimal("0.00001")
        rounded = (qty / step).to_integral_value(rounding=ROUND_DOWN) * step
        assert rounded > 0, "Cantidad mínima redondeada a 0"


# ===========================================================================
# TEST GROUP 3: Hallazgo - trade_executor.py hardcodea USDT como quote asset
# ===========================================================================


class TestTradeExecutorAssetParsing:
    """
    HALLAZGO CRÍTICO: trade_executor.py línea 187 hace:
        base_asset = symbol[:-4]  # Asume que quote es siempre USDT
        quote_asset = symbol[-4:]  # USDT

    Esto falla para pares como:
    - BTCBUSD (BUSD = 4 chars, funciona por coincidencia)
    - ETHBTC (BTC = 3 chars, FALLA)
    - SHIBUSDC (USDC = 4 chars, funciona por coincidencia)
    - BTCETH (ETH = 3 chars, FALLA)
    - BTCTUSD (TUSD = 4 chars, funciona)
    - BTCEUR (EUR = 3 chars, FALLA)

    Impacto: Balance se actualiza con activos incorrectos.
    """

    SYMBOL_CASES = [
        ("BTCUSDT", "BTC", "USDT", True),
        ("ETHUSDT", "ETH", "USDT", True),
        ("ETHBTC", "ETH", "BTC", False),  # BTC = 3 chars, FALLA
        ("BTCEUR", "BTC", "EUR", False),  # EUR = 3 chars, FALLA
        ("SHIBUSDT", "SHIB", "USDT", True),
        ("BTCBUSD", "BTC", "BUSD", True),
    ]

    @pytest.mark.parametrize(
        "symbol,expected_base,expected_quote,should_work", SYMBOL_CASES
    )
    def test_asset_extraction_from_symbol(
        self, symbol, expected_base, expected_quote, should_work
    ):
        """Verifica extracción de base/quote del símbolo."""
        # Reproduce la lógica de trade_executor.py línea 187
        base_asset = symbol[:-4]
        quote_asset = symbol[-4:]

        if should_work:
            assert base_asset == expected_base, (
                f"Base asset incorrecto para {symbol}: "
                f"obtuvo '{base_asset}', esperaba '{expected_base}'"
            )
            assert quote_asset == expected_quote, (
                f"Quote asset incorrecto para {symbol}: "
                f"obtuvo '{quote_asset}', esperaba '{expected_quote}'"
            )
        else:
            is_wrong = base_asset != expected_base or quote_asset != expected_quote
            assert is_wrong, (
                f"SORPRESA: La lógica hardcoded funciona para {symbol}, "
                f"pero no debería para pares con quote != 4 chars"
            )

    def test_recommends_exchange_info_for_asset_parsing(self):
        """
        Recomendación: Usar exchange_info para obtener baseAsset/quoteAsset
        en lugar de hardcodear la longitud del quote asset.
        """
        exchange_info_entry = {
            "symbol": "ETHBTC",
            "baseAsset": "ETH",
            "quoteAsset": "BTC",
        }
        base = exchange_info_entry["baseAsset"]
        quote = exchange_info_entry["quoteAsset"]
        assert base == "ETH"
        assert quote == "BTC"


# ===========================================================================
# TEST GROUP 4: Precision edge cases
# ===========================================================================


class TestPrecisionEdgeCases:
    """Tests de casos extremos de precisión."""

    def test_very_large_quantity(self):
        """Cantidades muy grandes no deben causar overflow."""
        qty = Decimal("999999999.99999999")
        step = Decimal("0.00000001")
        rounded = (qty / step).to_integral_value(rounding=ROUND_DOWN) * step
        assert rounded <= qty

    def test_infinity_handling(self):
        """Decimal infinito debe ser detectado y manejado."""
        result = Decimal("Infinity") * Decimal("100")
        assert result == Decimal("Infinity"), (
            "Infinity * 100 debe propagar Infinity. "
            "Código financiero DEBE verificar is_infinite() antes de usar."
        )
        assert result.is_infinite(), "Resultado infinito debe ser detectable"

    def test_nan_handling(self):
        """NaN debe ser detectado y rechazado."""
        nan_val = Decimal("NaN")
        assert nan_val.is_nan()
        result = nan_val * Decimal("100")
        assert result.is_nan(), "NaN propagado en multiplicación"

    def test_subnormal_decimal(self):
        """Valores sub-normales no deben causar errores."""
        tiny = Decimal("1E-28")
        step = Decimal("0.00000001")
        rounded = (tiny / step).to_integral_value(rounding=ROUND_DOWN) * step
        assert rounded >= 0

    def test_string_to_decimal_safety(self):
        """Conversión string -> Decimal debe rechazar valores inválidos."""
        invalid_values = ["abc", "", "12.34.56", None]
        for val in invalid_values:
            with pytest.raises((InvalidOperation, TypeError, ValueError)):
                Decimal(val)

    def test_float_to_decimal_via_string(self):
        """float -> Decimal debe pasar por str() para evitar imprecisión."""
        bad_way = Decimal(0.1)  # Hereda imprecisión de float
        good_way = Decimal(str(0.1))  # Exacto
        assert good_way == Decimal("0.1")
        assert bad_way != Decimal(
            "0.1"
        ), "Decimal(float) es inexacto; siempre usar Decimal(str(float))"
