"""
Tests P1 (FASE 3) — app/services/reconciliation_service.py
─────────────────────────────────────────────────────────────────
Objetivo: subir cobertura de 21% → ≥80% (TESTING_RULES.md §3).

Cubre la deuda alta §7:
  - has_internal_accounting=False path (estado actual de producción).
  - Cálculo de portfolio_total_usdt con tickers múltiples.
  - Errores de Binance: account_info vacío / sin balances.
  - Métricas Prometheus: portfolio_total_value_usdt, cash_balance_usdt,
    reconciliation_latency_seconds, balance_discrepancy_usd.
  - Ticker error en activo individual: no rompe el ciclo.
  - Breaker NO se activa cuando has_internal_accounting=False.

Política:
  - 100% offline (TESTING_RULES §1).
  - Decimal y casts explícitos para precios.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.reconciliation_service import ReconciliationService


# ─────────────────────────────────────────────────────────────────
# Helpers / Fixtures
# ─────────────────────────────────────────────────────────────────


def _account_info(usdt: float = 1000.0, btc: float = 0.5, eth: float = 2.0) -> dict:
    return {
        "balances": [
            {"asset": "USDT", "free": str(usdt), "locked": "0"},
            {"asset": "BTC", "free": str(btc), "locked": "0"},
            {"asset": "ETH", "free": str(eth), "locked": "0"},
            {"asset": "DOGE", "free": "0", "locked": "0"},  # se filtra (total=0)
        ]
    }


@pytest.fixture
def breakers() -> AsyncMock:
    cb = AsyncMock()
    cb.activate_breaker = AsyncMock(return_value=True)
    return cb


@pytest.fixture
def service(breakers) -> ReconciliationService:
    client = MagicMock()
    return ReconciliationService(client=client, breakers=breakers, threshold_pct=0.01)


# ─────────────────────────────────────────────────────────────────
# Path feliz: has_internal_accounting=False
# ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_reconciliation_ok_calcula_portfolio_total(service, breakers):
    singleton = MagicMock()
    singleton.get_account_info.return_value = _account_info(usdt=1000, btc=0.5, eth=2.0)
    singleton.client.get_symbol_ticker.side_effect = lambda symbol: {
        "BTCUSDT": {"price": "60000.0"},
        "ETHUSDT": {"price": "3000.0"},
    }[symbol]

    with patch(
        "app.services.reconciliation_service.get_binance_client_singleton",
        return_value=singleton,
    ):
        result = await service.run_reconciliation_cycle()

    # 1000 USDT + (0.5 * 60000) + (2 * 3000) = 1000 + 30000 + 6000 = 37000
    assert result["status"] == "ok"
    assert result["ext_usdt"] == 1000.0
    assert result["portfolio_total_usdt"] == 37000.0
    assert result["int_usdt"] == 1000.0
    # has_internal_accounting=False → discrepancia siempre 0, no se activa breaker
    assert result["discrepancy_usd"] == 0.0
    assert "latency_seconds" in result
    breakers.activate_breaker.assert_not_called()


@pytest.mark.asyncio
async def test_run_reconciliation_ok_filtra_balances_cero(service):
    """DOGE con free=0 y locked=0 NO debe contarse en balances."""
    singleton = MagicMock()
    singleton.get_account_info.return_value = _account_info()
    singleton.client.get_symbol_ticker.return_value = {"price": "60000.0"}

    with patch(
        "app.services.reconciliation_service.get_binance_client_singleton",
        return_value=singleton,
    ):
        result = await service.run_reconciliation_cycle()

    assert result["status"] == "ok"


@pytest.mark.asyncio
async def test_run_reconciliation_ticker_error_no_rompe_ciclo(service):
    """Si get_symbol_ticker falla en un activo, ese asset suma 0 al total."""
    singleton = MagicMock()
    singleton.get_account_info.return_value = {
        "balances": [
            {"asset": "USDT", "free": "1000", "locked": "0"},
            {"asset": "FOO", "free": "100", "locked": "0"},  # FOOUSDT no existe
        ]
    }
    singleton.client.get_symbol_ticker.side_effect = RuntimeError("FOOUSDT not found")

    with patch(
        "app.services.reconciliation_service.get_binance_client_singleton",
        return_value=singleton,
    ):
        result = await service.run_reconciliation_cycle()

    assert result["status"] == "ok"
    assert result["portfolio_total_usdt"] == 1000.0  # solo USDT


@pytest.mark.asyncio
async def test_run_reconciliation_solo_usdt(service):
    """Sin altcoins, total_value == ext_usdt."""
    singleton = MagicMock()
    singleton.get_account_info.return_value = {
        "balances": [{"asset": "USDT", "free": "500", "locked": "0"}]
    }

    with patch(
        "app.services.reconciliation_service.get_binance_client_singleton",
        return_value=singleton,
    ):
        result = await service.run_reconciliation_cycle()

    assert result["portfolio_total_usdt"] == 500.0
    assert result["ext_usdt"] == 500.0


@pytest.mark.asyncio
async def test_run_reconciliation_balance_locked_se_suma(service):
    """free + locked deben sumarse para el total por asset."""
    singleton = MagicMock()
    singleton.get_account_info.return_value = {
        "balances": [
            {"asset": "USDT", "free": "300", "locked": "200"},  # total 500
            {"asset": "BTC", "free": "0.1", "locked": "0.1"},  # total 0.2
        ]
    }
    singleton.client.get_symbol_ticker.return_value = {"price": "50000.0"}

    with patch(
        "app.services.reconciliation_service.get_binance_client_singleton",
        return_value=singleton,
    ):
        result = await service.run_reconciliation_cycle()

    # 500 USDT + (0.2 * 50000) = 500 + 10000 = 10500
    assert result["ext_usdt"] == 500.0
    assert result["portfolio_total_usdt"] == 10500.0


# ─────────────────────────────────────────────────────────────────
# Errores de Binance / inputs inválidos
# ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_reconciliation_account_info_vacio(service):
    singleton = MagicMock()
    singleton.get_account_info.return_value = None

    with patch(
        "app.services.reconciliation_service.get_binance_client_singleton",
        return_value=singleton,
    ):
        result = await service.run_reconciliation_cycle()

    assert result["status"] == "error"
    assert "No account info" in result["error"]


@pytest.mark.asyncio
async def test_run_reconciliation_account_info_sin_balances(service):
    singleton = MagicMock()
    singleton.get_account_info.return_value = {"foo": "bar"}  # sin 'balances'

    with patch(
        "app.services.reconciliation_service.get_binance_client_singleton",
        return_value=singleton,
    ):
        result = await service.run_reconciliation_cycle()

    assert result["status"] == "error"


@pytest.mark.asyncio
async def test_run_reconciliation_excepcion_se_captura(service):
    singleton = MagicMock()
    singleton.get_account_info.side_effect = ConnectionError("API down")

    with patch(
        "app.services.reconciliation_service.get_binance_client_singleton",
        return_value=singleton,
    ):
        result = await service.run_reconciliation_cycle()

    assert result["status"] == "error"
    assert "API down" in result["error"]
    assert "latency_seconds" in result


# ─────────────────────────────────────────────────────────────────
# Breaker: has_internal_accounting=False NO debe activarlo
# ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_breaker_no_se_activa_sin_contabilidad_interna(service, breakers):
    """
    Documenta el invariante actual de §7: el path
    `has_internal_accounting=False` SIEMPRE produce discrepancy=0.0,
    por lo que el breaker `system_integrity` NO debe dispararse.
    """
    singleton = MagicMock()
    singleton.get_account_info.return_value = {
        "balances": [{"asset": "USDT", "free": "0.0001", "locked": "0"}]
    }

    with patch(
        "app.services.reconciliation_service.get_binance_client_singleton",
        return_value=singleton,
    ):
        await service.run_reconciliation_cycle()

    breakers.activate_breaker.assert_not_called()


# ─────────────────────────────────────────────────────────────────
# Métricas Prometheus
# ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_metricas_se_actualizan(service):
    singleton = MagicMock()
    singleton.get_account_info.return_value = _account_info(usdt=100, btc=0, eth=0)

    with patch(
        "app.services.reconciliation_service.get_binance_client_singleton",
        return_value=singleton,
    ), patch(
        "app.services.reconciliation_service.portfolio_total_value_usdt"
    ) as mock_total, patch(
        "app.services.reconciliation_service.cash_balance_usdt"
    ) as mock_cash, patch(
        "app.services.reconciliation_service.reconciliation_latency_seconds"
    ) as mock_latency, patch(
        "app.services.reconciliation_service.balance_discrepancy_usd"
    ) as mock_disc, patch(
        "app.services.reconciliation_service.unaccounted_pnl_usd"
    ) as mock_pnl:
        mock_total.labels.return_value = MagicMock()
        mock_cash.labels.return_value = MagicMock()
        await service.run_reconciliation_cycle()

    mock_total.labels.assert_called_with(strategy="grid")
    mock_cash.labels.assert_called_with(strategy="grid")
    mock_latency.observe.assert_called_once()
    mock_disc.set.assert_called_with(0.0)
    mock_pnl.set.assert_called_with(0.0)


@pytest.mark.asyncio
async def test_metrica_latency_se_observa_aun_en_error(service):
    singleton = MagicMock()
    singleton.get_account_info.side_effect = RuntimeError("boom")

    with patch(
        "app.services.reconciliation_service.get_binance_client_singleton",
        return_value=singleton,
    ), patch(
        "app.services.reconciliation_service.reconciliation_latency_seconds"
    ) as mock_latency:
        result = await service.run_reconciliation_cycle()

    assert result["status"] == "error"
    mock_latency.observe.assert_called_once()


# ─────────────────────────────────────────────────────────────────
# Constructor / configuración
# ─────────────────────────────────────────────────────────────────


def test_constructor_setea_threshold_default():
    cli, brk = MagicMock(), AsyncMock()
    s = ReconciliationService(client=cli, breakers=brk)
    assert s._threshold_pct == 0.01
    assert s._running is False


def test_constructor_threshold_custom():
    cli, brk = MagicMock(), AsyncMock()
    s = ReconciliationService(client=cli, breakers=brk, threshold_pct=0.05)
    assert s._threshold_pct == 0.05
