"""L0 paper: GRID_CONFIG_FILE en el ciclo + sizer piso 15 / nivel 20.

TDD · paper-only · mocks de Binance · PROMOTE_LIVE: NO.
No toca freeze JSON ni paper_telemetry.
"""

from __future__ import annotations

import inspect
import json
from decimal import ROUND_UP, Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import app.services.trading_tasks as tt
from app.core.optimized_grid_manager import (
    AssetConfig,
    GridManagerConfig,
    OptimizedGridManager,
    create_optimized_grid_manager,
    resolve_grid_config_file,
)
from app.scheduler.optimized_scheduler import OptimizedGridScheduler

pytestmark = [pytest.mark.usefixtures("paper_env")]

PRICE_L0 = Decimal("1886.8")
STEP_L0 = Decimal("0.0001")
FREEZE_QTY = Decimal("0.010399")
LEVEL_NOTIONAL = Decimal("20")
FLOOR_NOTIONAL = Decimal("15")
EXCHANGE_MIN_NOTIONAL = Decimal("10")


def _ceil_to_step(qty: Decimal, step: Decimal) -> Decimal:
    return (qty / step).to_integral_value(rounding=ROUND_UP) * step


def _expected_l0_qty() -> Decimal:
    """20 / 1886.8 ≈ 0.0106005 → ceil step 0.0001 = 0.0107 (0.0106 * 1886.8 < 20)."""
    return _ceil_to_step(LEVEL_NOTIONAL / PRICE_L0, STEP_L0)


def test_resolve_grid_config_file_reads_env(monkeypatch):
    monkeypatch.setenv("GRID_CONFIG_FILE", "/tmp/foo.json")
    assert resolve_grid_config_file() == "/tmp/foo.json"

    monkeypatch.setenv("GRID_CONFIG_FILE", "  ")
    assert resolve_grid_config_file() == "grid_config_optimized.json"

    monkeypatch.delenv("GRID_CONFIG_FILE", raising=False)
    assert resolve_grid_config_file() == "grid_config_optimized.json"


def test_trading_tasks_call_sites_use_helper():
    source = inspect.getsource(tt)
    hardcoded = 'create_optimized_grid_manager("grid_config_optimized.json")'
    assert hardcoded not in source
    assert source.count("resolve_grid_config_file()") >= 4
    assert "create_optimized_grid_manager(resolve_grid_config_file())" in source


def test_execute_trading_cycle_passes_env_config_file(monkeypatch):
    monkeypatch.setenv("GRID_CONFIG_FILE", "/tmp/foo.json")
    monkeypatch.setenv("PAPER_TRADING", "true")
    monkeypatch.setenv("FORCE_REAL_MODE", "")
    monkeypatch.setenv("CELERY_BROKER_URL", "memory://")
    monkeypatch.setenv("CELERY_RESULT_BACKEND", "cache+memory://")

    singleton = MagicMock()
    singleton.validate_credentials_and_connectivity.return_value = {
        "net_ok": True,
        "auth_ok": True,
    }
    create = AsyncMock(return_value=None)
    monkeypatch.setattr(tt, "get_binance_client_singleton", lambda: singleton)
    monkeypatch.setattr(tt, "get_shared_breakers", lambda: MagicMock())
    monkeypatch.setattr(tt, "create_optimized_grid_manager", create)
    monkeypatch.setattr(tt, "maybe_deactivate_stale_system_integrity", lambda _ck: False)

    result = tt.execute_trading_cycle.__wrapped__()

    assert result["status"] == "error"
    create.assert_awaited()
    args, kwargs = create.call_args
    path = args[0] if args else kwargs.get("config_file")
    assert path == "/tmp/foo.json"
    assert path != "grid_config_optimized.json"


def test_scheduler_default_respects_grid_config_file_env(monkeypatch):
    monkeypatch.setenv("GRID_CONFIG_FILE", "/tmp/foo.json")
    scheduler = OptimizedGridScheduler()
    assert scheduler.config_file == "/tmp/foo.json"

    explicit = OptimizedGridScheduler(config_file="explicit_grid.json")
    assert explicit.config_file == "explicit_grid.json"

    monkeypatch.delenv("GRID_CONFIG_FILE", raising=False)
    fallback = OptimizedGridScheduler()
    assert fallback.config_file == "grid_config_optimized.json"


def _freeze_style_payload() -> dict:
    return {
        "_config_metadata": {
            "version": "l0_paper_window_v1",
            "min_notional_floor_usd": "15.00",
            "notional_per_level_usd": "20.00",
            "paper_only": True,
        },
        "system_config": {"paper_trading": True, "force_real_mode": False},
        "ETHUSDT": {
            "symbol": "ETHUSDT",
            "min_price": 1800.0,
            "max_price": 2200.0,
            "grids": 10,
            "quantity": 0.010399,
            "notional_per_level_usd": 20.0,
            "is_active": True,
        },
    }


def _optimized_style_payload() -> dict:
    return {
        "ETHUSDT": {
            "symbol": "ETHUSDT",
            "min_price": 1800.0,
            "max_price": 2200.0,
            "grids": 10,
            "quantity": 0.0025,
            "is_active": True,
        },
        "update_interval": 60,
    }


async def _factory_from_payload(tmp_path: Path, payload: dict):
    cfg_path = tmp_path / "grid_cfg.json"
    cfg_path.write_text(json.dumps(payload))
    client = MagicMock()
    client.api_key = "paper-key"
    singleton = MagicMock(client=client)
    with patch(
        "app.services.binance_client_singleton.binance_client_singleton",
        singleton,
    ), patch(
        "app.core.optimized_grid_manager.OrderValidator", return_value=MagicMock()
    ), patch(
        "app.core.optimized_grid_manager.AsyncBinanceWrapper"
    ), patch.object(
        OptimizedGridManager, "_load_asset_limits", AsyncMock()
    ):
        return await create_optimized_grid_manager(str(cfg_path))


@pytest.mark.anyio
async def test_factory_l0_min_notional_threshold_is_20(tmp_path: Path):
    manager = await _factory_from_payload(tmp_path, _freeze_style_payload())
    assert manager is not None
    assert Decimal(str(manager.config.min_notional_threshold)) == LEVEL_NOTIONAL


@pytest.mark.anyio
async def test_factory_without_l0_metadata_keeps_default_10(tmp_path: Path):
    manager = await _factory_from_payload(tmp_path, _optimized_style_payload())
    assert manager is not None
    assert Decimal(str(manager.config.min_notional_threshold)) == Decimal("10")


def _manager_with_sizer(*, threshold: Decimal, quantity: Decimal) -> OptimizedGridManager:
    client = MagicMock()
    client.api_key = "paper-key"
    singleton = MagicMock(client=client)
    singleton.get_account_info.return_value = {"accountType": "SPOT", "balances": []}
    cfg = GridManagerConfig(
        assets={
            "ETHUSDT": AssetConfig(
                symbol="ETHUSDT",
                min_price=1800.0,
                max_price=2200.0,
                grids=10,
                quantity=float(quantity),
            )
        },
        update_interval=60,
        min_notional_threshold=float(threshold),
    )
    with patch(
        "app.services.binance_client_singleton.binance_client_singleton",
        singleton,
    ), patch(
        "app.core.optimized_grid_manager.OrderValidator", return_value=MagicMock()
    ), patch(
        "app.core.optimized_grid_manager.AsyncBinanceWrapper"
    ):
        manager = OptimizedGridManager(cfg)
    manager.asset_limits["ETHUSDT"] = SimpleNamespace(
        min_notional=float(EXCHANGE_MIN_NOTIONAL),
        step_size=float(STEP_L0),
    )
    return manager


def test_calculate_optimal_quantities_l0_bumps_to_min_notional_20():
    manager = _manager_with_sizer(threshold=LEVEL_NOTIONAL, quantity=FREEZE_QTY)
    expected = _expected_l0_qty()
    with patch(
        "app.core.paper_equity_ledger.paper_equity_is_source_of_truth",
        return_value=True,
    ), patch(
        "app.core.paper_cycle_liquidity.can_afford_grid_quantity",
        return_value=True,
    ):
        quantities = manager.calculate_optimal_quantities(
            {"ETH": 1.0, "USDT": 1000.0},
            {"ETHUSDT": float(PRICE_L0)},
        )

    qty = Decimal(str(quantities["ETHUSDT"]))
    notional = qty * PRICE_L0
    # Cap histórico 0.003 ETH queda inerte: 0.003 * 1886.8 ≈ 5.66 < 20.
    historical_cap = Decimal("0.003")
    assert historical_cap * PRICE_L0 < LEVEL_NOTIONAL
    assert qty != Decimal("0.0053")
    assert qty == expected
    assert qty >= Decimal("0.0106")
    assert notional >= LEVEL_NOTIONAL
    assert qty == _ceil_to_step(qty, STEP_L0)


def test_calculate_optimal_quantities_optimized_default_threshold_10():
    """Regresión: sin L0, threshold 10 no debe forzar el bump a 20."""
    manager = _manager_with_sizer(threshold=Decimal("10"), quantity=Decimal("0.0025"))
    with patch(
        "app.core.paper_equity_ledger.paper_equity_is_source_of_truth",
        return_value=True,
    ), patch(
        "app.core.paper_cycle_liquidity.can_afford_grid_quantity",
        return_value=True,
    ):
        quantities = manager.calculate_optimal_quantities(
            {"ETH": 1.0, "USDT": 1000.0},
            {"ETHUSDT": float(PRICE_L0)},
        )

    qty = Decimal(str(quantities["ETHUSDT"]))
    notional = qty * PRICE_L0
    assert Decimal(str(manager.config.min_notional_threshold)) == Decimal("10")
    assert notional >= EXCHANGE_MIN_NOTIONAL
    assert qty < Decimal("0.0106")
