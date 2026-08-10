"""COV-1.5 — balance_validator + integrity_monitor (paper mocks, sin red)."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def bv(paper_env):
    with (
        patch("app.core.balance_validator.binance_client_singleton", MagicMock()),
        patch("app.core.balance_validator.Database", return_value=MagicMock()),
        patch("app.core.balance_validator.TelegramBot", return_value=MagicMock()),
        patch("app.core.balance_validator.GrafanaMetrics", return_value=MagicMock()),
        patch(
            "app.core.balance_validator.get_shared_breakers",
            return_value=MagicMock(activate_breaker=AsyncMock()),
        ),
        patch("app.core.balance_validator.settings", SimpleNamespace()),
    ):
        from app.core.balance_validator import BalanceValidator

        v = BalanceValidator()
        v.telegram_bot.send_alert = AsyncMock()
        v.grafana_metrics.record_metric = AsyncMock()
        v.db.insert_validation_record = AsyncMock()
        v.db.get_system_state = AsyncMock(
            return_value={
                "balances": {
                    "USDT": {"quantity": "100", "value": "100", "last_updated": "t"}
                }
            }
        )
        v.circuit_breakers.activate_breaker = AsyncMock()
        v.circuit_breakers.activate_critical_mode = AsyncMock()
        yield v


@pytest.fixture
def im(paper_env):
    with (
        patch("app.core.integrity_monitor.Database", return_value=MagicMock()),
        patch("app.core.integrity_monitor.TelegramBot", return_value=MagicMock()),
        patch("app.core.integrity_monitor.GrafanaMetrics", return_value=MagicMock()),
        patch(
            "app.core.integrity_monitor.get_shared_breakers",
            return_value=MagicMock(
                activate_critical_mode=AsyncMock(),
                deactivate_critical_mode=AsyncMock(),
                is_critical_mode_active=MagicMock(return_value=False),
            ),
        ),
        patch("app.core.integrity_monitor.settings", SimpleNamespace()),
    ):
        from app.core.integrity_monitor import IntegrityMonitor

        m = IntegrityMonitor()
        m.telegram_bot.send_alert = AsyncMock()
        m.grafana_metrics.record_metric = AsyncMock()
        m.db.execute_query = AsyncMock(return_value=1)
        m.db.insert_integrity_record = AsyncMock()
        # fuera de grace para umbrales
        m.startup_grace_seconds = 0
        m.required_consecutive_critical = 1
        yield m


# ── balance_validator ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_bv_compare_exact_zero_and_critical(bv):
    discs = await bv.compare_balances(
        {"total_balance": Decimal("100"), "source": "sys"},
        {"total_balance": Decimal("100"), "source": "bn"},
    )
    assert discs == []

    discs = await bv.compare_balances(
        {"total_balance": Decimal("120"), "source": "sys"},
        {"total_balance": Decimal("100"), "source": "bn"},
    )
    assert len(discs) == 1
    assert discs[0]["severity"] == "CRITICAL"
    bv.circuit_breakers.activate_breaker.assert_awaited()


@pytest.mark.asyncio
async def test_bv_severity_and_handle(bv):
    assert bv.calculate_discrepancy_severity(Decimal("0.001")) == "LOW"
    assert bv.calculate_discrepancy_severity(Decimal("0.02")) == "HIGH"
    assert bv.calculate_discrepancy_severity(Decimal("0.10")) == "CRITICAL"

    disc_shape = {
        "asset": "USDT",
        "system_value": 120.0,
        "binance_value": 100.0,
        "value_difference": 20.0,
        "value_difference_pct": 0.2,
    }
    await bv.handle_discrepancies(
        [
            {**disc_shape, "severity": "CRITICAL", "type": "TOTAL"},
            {**disc_shape, "severity": "HIGH", "type": "TOTAL"},
        ]
    )
    assert bv.telegram_bot.send_alert.await_count >= 2
    bv.circuit_breakers.activate_critical_mode.assert_awaited()


@pytest.mark.asyncio
async def test_bv_get_prices_and_balances(bv, tmp_path, monkeypatch):
    cfg = tmp_path / "grid_config_optimized.json"
    cfg.write_text(
        '{"_safe_config_metadata":{"system_reported_balance":"500",'
        '"real_balance_binance":"480"},"assets":{}}',
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    assert await bv.get_system_total_balance() == Decimal("500")
    assert await bv.get_real_binance_balance() == Decimal("480")
    sys_b = await bv.get_system_balances()
    assert sys_b["total_balance"] == Decimal("500")
    bn = await bv.get_binance_balances()
    assert bn["total_balance"] == Decimal("480")

    assert await bv.get_asset_price("USDT") == Decimal("1.0")
    bv.binance_client.get_symbol_price.return_value = {"price": "2500"}
    assert await bv.get_asset_price("ETH") == Decimal("2500")

    legacy = await bv.get_system_balances_legacy()
    assert "USDT" in legacy


@pytest.mark.asyncio
async def test_bv_validate_and_force(bv):
    with (
        patch.object(
            bv,
            "get_system_balances",
            AsyncMock(return_value={"total_balance": Decimal("100"), "source": "s"}),
        ),
        patch.object(
            bv,
            "get_binance_balances",
            AsyncMock(return_value={"total_balance": Decimal("100"), "source": "b"}),
        ),
        patch.object(bv, "update_grafana_metrics", AsyncMock()),
        patch.object(bv, "log_validation_result", AsyncMock()),
        patch.object(bv, "update_integrity_metrics", AsyncMock()),
    ):
        await bv.validate_balances()
        assert bv.total_validations == 1
        forced = await bv.force_balance_validation()
        assert forced["status"] == "success"
        assert forced["discrepancies"] == []


@pytest.mark.asyncio
async def test_bv_correct_and_auto(bv, tmp_path, monkeypatch):
    cfg = tmp_path / "grid_config_optimized.json"
    cfg.write_text(
        '{"_safe_config_metadata":{"real_balance_binance":"320","system_reported_balance":"400"}}',
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    assert await bv.correct_system_balance(Decimal("320")) is True
    with patch.object(
        bv,
        "force_balance_validation",
        AsyncMock(return_value={"status": "success", "discrepancies": []}),
    ):
        out = await bv.auto_correct_balance_discrepancy()
    assert out["status"] == "success"

    summary = await bv.get_validation_summary()
    assert "integrity_score" in summary
    await bv.update_thresholds(alert_threshold=0.02, critical_threshold=0.08)
    assert bv.alert_threshold == Decimal("0.02")


@pytest.mark.asyncio
async def test_bv_metrics_and_alerts(bv):
    bv.db.insert_discrepancy_record = AsyncMock()
    bv.db.update_system_metrics = AsyncMock()
    with (
        patch.object(bv, "get_system_balances", AsyncMock(return_value={"total_balance": Decimal("100"), "source": "s"})),
        patch.object(bv, "get_binance_balances", AsyncMock(return_value={"total_balance": Decimal("100"), "source": "b"})),
        patch.object(bv, "update_grafana_metrics", AsyncMock()),
        patch.object(bv, "log_validation_result", AsyncMock()),
    ):
        await bv.update_validation_metrics([])
        await bv.update_grafana_metrics([])
        await bv.log_validation_result([])
        await bv.log_discrepancies(
            [{"type": "TOTAL", "severity": "LOW", "total_difference_pct": 0.1}]
        )
        await bv.update_integrity_metrics([])
        disc = {
            "asset": "USDT",
            "system_value": 110.0,
            "binance_value": 100.0,
            "value_difference": 10.0,
            "value_difference_pct": 0.1,
        }
        await bv.send_critical_alert([disc])
        await bv.send_high_alert([disc])
        await bv.activate_critical_circuit_breakers()
        await bv.force_validation()
        assert bv.total_validations >= 1


# ── integrity_monitor ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_im_set_components_and_checks(im):
    bal = MagicMock(integrity_score=95.0, last_validation=datetime.now())
    ops = MagicMock()
    ops.get_operation_summary = AsyncMock(
        return_value={"success_rate": 0.98, "failed_operations": 1, "partial_fills": 2}
    )
    ops.get_failed_operations_summary = AsyncMock(return_value=[])
    im.set_components(bal, ops)

    assert await im.check_balance_integrity() == 95.0
    assert await im.check_operation_integrity() > 90
    assert await im.check_system_integrity() == 100.0
    assert await im.check_database_health() == 100.0
    assert await im.check_binance_health() == 100.0
    assert await im.check_system_metrics() == 100.0


@pytest.mark.asyncio
async def test_im_comprehensive_and_thresholds(im):
    with (
        patch.object(im, "check_balance_integrity", AsyncMock(return_value=90.0)),
        patch.object(im, "check_operation_integrity", AsyncMock(return_value=90.0)),
        patch.object(im, "check_system_integrity", AsyncMock(return_value=90.0)),
    ):
        await im.perform_comprehensive_check()
    assert im.overall_integrity_score == 90.0
    assert im.last_comprehensive_check is not None

    im.overall_integrity_score = 60.0
    await im.check_integrity_thresholds()
    im.telegram_bot.send_alert.assert_awaited()
    im.circuit_breakers.activate_critical_mode.assert_awaited()

    im.overall_integrity_score = 80.0
    im.consecutive_overall_critical = 0
    await im.check_integrity_thresholds()

    im.overall_integrity_score = 96.0
    im.critical_alerts_count = 1
    im.warning_alerts_count = 1
    await im.check_integrity_thresholds()


@pytest.mark.asyncio
async def test_im_critical_check_and_alerts(im):
    bal = MagicMock(integrity_score=40.0, last_validation=datetime.now())
    ops = MagicMock()
    ops.get_failed_operations_summary = AsyncMock(return_value=list(range(12)))
    im.set_components(bal, ops)
    await im.perform_critical_check()
    assert im.consecutive_critical_checks >= 1

    await im.trigger_critical_integrity_alert()
    await im.trigger_warning_integrity_alert()
    await im.trigger_critical_alert(["x"])
    await im.trigger_health_recovery_alert()
    await im.activate_critical_circuit_breakers()
    await im.update_integrity_metrics()
    await im.log_integrity_check()

    report = await im.generate_health_report()
    assert "Score de Integridad" in report
    im.db.insert_health_report = AsyncMock()
    await im.log_health_report(report)
    summary = await im.get_integrity_summary()
    assert "overall_integrity_score" in summary

    with patch.object(im, "perform_comprehensive_check", AsyncMock()):
        await im.force_integrity_check()
    await im.update_monitoring_config(check_interval=10, critical_check_interval=5)
    await im.stop_monitoring()
    assert im.monitoring_active is False


@pytest.mark.asyncio
async def test_im_stale_balance_penalty(im):
    bal = MagicMock(
        integrity_score=100.0,
        last_validation=datetime.now() - timedelta(seconds=2000),
    )
    im.set_components(bal, None)
    score = await im.check_balance_integrity()
    assert score == pytest.approx(80.0)


@pytest.mark.asyncio
async def test_bv_error_and_api_fallback(bv):
    with patch.object(
        bv, "get_system_balances", AsyncMock(side_effect=RuntimeError("boom"))
    ):
        await bv.validate_balances()
    assert bv.consecutive_failures >= 1

    bv.binance_client.get_account_info.return_value = {
        "balances": [
            {"asset": "ETH", "free": "0.1", "locked": "0"},
            {"asset": "USDT", "free": "0", "locked": "0"},
        ]
    }
    with (
        patch.object(bv, "get_real_binance_balance", AsyncMock(return_value=Decimal("0"))),
        patch.object(bv, "get_asset_price", AsyncMock(return_value=Decimal("2000"))),
    ):
        bn = await bv.get_binance_balances()
    assert "ETH" in bn

    bv.config = SimpleNamespace(
        _safe_config_metadata={"real_balance_binance": 1.0}
    )
    assert await bv.update_real_binance_balance(Decimal("333"), Decimal("1"), Decimal("0.1"))


@pytest.mark.asyncio
async def test_im_grace_period_skips_critical(im):
    im.startup_time = datetime.now()
    im.startup_grace_seconds = 9999
    im.overall_integrity_score = 10.0
    im.telegram_bot.send_alert.reset_mock()
    await im.check_integrity_thresholds()
    im.telegram_bot.send_alert.assert_not_awaited()


@pytest.mark.asyncio
async def test_im_recovery_from_critical_mode(im):
    im.startup_grace_seconds = 0
    im.overall_integrity_score = 96.0
    im.critical_alerts_count = 2
    im.recovery_cycles = 1
    im.circuit_breakers.is_critical_mode_active.return_value = True
    await im.check_integrity_thresholds()
    im.circuit_breakers.deactivate_critical_mode.assert_awaited()


@pytest.mark.asyncio
async def test_im_ops_penalties(im):
    ops = MagicMock()
    ops.get_operation_summary = AsyncMock(
        return_value={
            "success_rate": 0.9,
            "failed_operations": 10,
            "partial_fills": 20,
        }
    )
    im.set_components(None, ops)
    score = await im.check_operation_integrity()
    assert score < 90
    assert await im.check_balance_integrity() == 100.0  # sin validator


@pytest.mark.asyncio
async def test_im_start_and_loops_stop_fast(im):
    im.monitoring_active = False
    with patch("asyncio.create_task") as ct:
        await im.start_monitoring()
        assert ct.call_count == 3

    im.monitoring_active = True

    async def _stop_soon(*_a, **_k):
        im.monitoring_active = False

    with (
        patch.object(im, "perform_comprehensive_check", AsyncMock(side_effect=_stop_soon)),
        patch("asyncio.sleep", AsyncMock()),
    ):
        await im.comprehensive_monitoring_loop()
    im.monitoring_active = True
    with (
        patch.object(im, "perform_critical_check", AsyncMock(side_effect=_stop_soon)),
        patch("asyncio.sleep", AsyncMock()),
    ):
        await im.critical_monitoring_loop()
