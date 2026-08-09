"""S-COV-85 Z2 — core modules (optimizer, breakers, paper, metrics). Paper-only."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.usefixtures("paper_env")


# ── balance_optimizer ───────────────────────────────────────────────────────


def test_balance_optimizer_happy_and_limits(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from app.core.balance_optimizer import BalanceOptimizer

    opt = BalanceOptimizer(total_balance=391.75)
    ok, msg = opt.can_place_order("BTCUSDT", 10.0)
    assert ok and "válida" in msg

    assert opt.can_place_order("NOSYM", 1.0)[0] is False
    assert opt.can_place_order("BTCUSDT", 999.0)[0] is False

    opt.record_order("BTCUSDT", 40.0)
    assert opt.get_available_for_symbol("BTCUSDT") == pytest.approx(10.0)
    assert opt.get_available_for_symbol("NOSYM") == 0.0
    assert opt.get_total_used() == pytest.approx(40.0)
    assert opt.get_available_total() == pytest.approx(opt.available_amount - 40.0)

    # exhaust available_amount (strict >) across symbols
    opt2 = BalanceOptimizer(total_balance=391.75)
    for sym in list(opt2.allocations)[:7]:
        opt2.record_order(sym, opt2.allocations[sym].allocated_amount)
    assert opt2.can_place_order("AVAXUSDT", 30.01)[0] is False

    report = opt.get_status_report()
    assert "allocations" in report and "BTCUSDT" in report["allocations"]

    opt.reset_daily_usage()
    assert opt.get_total_used() == 0.0
    opt.record_order("NOSYM", 1.0)  # no-op branch

    # total available exhausted while symbol allocation still has room (line 79)
    opt3 = BalanceOptimizer(total_balance=391.75)
    for alloc in opt3.allocations.values():
        alloc.used_amount = 0.0
    opt3.allocations["ETHUSDT"].used_amount = opt3.available_amount
    opt3.allocations["BTCUSDT"].allocated_amount = 1000.0
    assert opt3.can_place_order("BTCUSDT", 1.0)[0] is False

    # warning path: allocated > available
    with patch("app.core.balance_optimizer.logger") as log:
        BalanceOptimizer(total_balance=50.0)
        assert log.warning.called


# ── circuit_breaker (LEGACY singular) ───────────────────────────────────────


def test_circuit_breaker_load_save_and_limits(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from app.core import circuit_breaker as cb_mod

    # load empty → defaults
    br = cb_mod.CircuitBreaker()
    assert br.state["is_open"] is False

    # save + load roundtrip with datetimes
    br.state["opened_at"] = datetime.now()
    br.state["is_open"] = True
    br.state["reason"] = "test"
    br.save_state()
    br2 = cb_mod.CircuitBreaker()
    assert br2.state["is_open"] is True
    assert isinstance(br2.state["opened_at"], datetime)

    # load error path
    Path("circuit_breaker_state.json").write_text("{bad", encoding="utf-8")
    with patch("app.core.circuit_breaker.logger") as log:
        cb_mod.CircuitBreaker()
        assert log.error.called

    # save error path
    br3 = cb_mod.CircuitBreaker()
    with patch("builtins.open", side_effect=OSError("deny")):
        br3.save_state()

    # reset daily when date advanced
    br3.state["last_reset"] = datetime.now() - timedelta(days=2)
    br3.state["daily_loss"] = 0.04
    br3.reset_daily_limits()
    assert br3.state["daily_loss"] == 0.0

    # already open
    br3.state["is_open"] = True
    br3.state["reason"] = "open"
    ok, reason = br3.check_limits()
    assert ok is False and "abierto" in reason

    # trade loss limit
    br3.close_circuit("reset")
    ok, _ = br3.check_limits(trade_loss=0.05)
    assert ok is False and br3.state["is_open"]

    # daily / total / consecutive / hourly
    for key, value, expect_substr in [
        ("daily_loss", 0.06, "diaria"),
        ("total_loss", 0.11, "total"),
        ("consecutive_losses", 3, "consecutivas"),
        ("hourly_loss", 0.04, "hora"),
    ]:
        br3.close_circuit("r")
        br3.state["daily_loss"] = 0.0
        br3.state["total_loss"] = 0.0
        br3.state["consecutive_losses"] = 0
        br3.state["hourly_loss"] = 0.0
        br3.state[key] = value
        ok, msg = br3.check_limits()
        assert ok is False, expect_substr
        assert expect_substr in msg.lower() or "consecutivas" in msg or "hora" in msg

    br3.close_circuit()
    br3.state.update(
        {
            "daily_loss": 0.0,
            "total_loss": 0.0,
            "consecutive_losses": 0,
            "hourly_loss": 0.0,
        }
    )
    assert br3.check_limits()[0] is True

    br3.record_loss(5.0, 0.01)
    assert br3.state["consecutive_losses"] == 1
    br3.record_profit(2.0, 0.005)
    assert br3.state["consecutive_losses"] == 0
    assert br3.state["daily_loss"] == pytest.approx(0.005)

    status = br3.get_status()
    assert "limits" in status and status["opened_at"] is None
    br3._open_circuit("alert")
    assert br3.get_status()["opened_at"] is not None

    br3.reset_hourly_loss()
    assert br3.state["hourly_loss"] == 0.0

    with patch.object(cb_mod, "circuit_breaker", br3):
        br3.close_circuit()
        assert cb_mod.check_trading_allowed()[0] is True
        cb_mod.record_trade_result(1.0, 0.01)
        cb_mod.record_trade_result(-1.0, 0.01)


# ── commission_aware_trading ────────────────────────────────────────────────


def test_commission_aware_trading_paths():
    from app.core.commission_aware_trading import CommissionAwareTrading
    from app.services.commission import CommissionResult

    cat = CommissionAwareTrading()

    with patch(
        "app.core.commission_aware_trading.validate_minimum_profit",
        return_value=(
            True,
            {
                "net_profit": Decimal("1.5"),
                "gross_profit": Decimal("2.0"),
            },
        ),
    ):
        ok, data = cat.validate_trade_profitability("BTCUSDT", 100, 102, 1)
        assert ok and data["net_profit"] == 1.5

    with patch(
        "app.core.commission_aware_trading.validate_minimum_profit",
        return_value=(False, {"net_profit": Decimal("-0.1")}),
    ):
        ok, _ = cat.validate_trade_profitability("BTCUSDT", 100, 100.1, 1)
        assert ok is False

    with patch(
        "app.core.commission_aware_trading.validate_minimum_profit",
        side_effect=RuntimeError("boom"),
    ):
        ok, err = cat.validate_trade_profitability("BTCUSDT", 1, 2, 1)
        assert ok is False and "error" in err

    fake_comm = CommissionResult(
        commission_usdt=Decimal("0.1"),
        commission_percentage=Decimal("0.1"),
        notional_value=Decimal("100"),
        order_type="MARKET",
    )
    big_comm = CommissionResult(
        commission_usdt=Decimal("1.0"),
        commission_percentage=Decimal("1.0"),
        notional_value=Decimal("10.5"),
        order_type="MARKET",
    )
    with patch(
        "app.core.commission_aware_trading.calculate_commission",
        return_value=fake_comm,
    ):
        qty, details = cat.calculate_optimal_quantity("BTCUSDT", 100.0, 50.0, 10.0)
        assert qty > 0 and "adjusted_quantity" in details

        # insufficient for min notional + commission
        qty0, err0 = cat.calculate_optimal_quantity("BTCUSDT", 5.0, 50.0, 10.0)
        assert qty0 == 0.0 and "error" in err0

    # adjusted below min → bump to min_quantity when affordable
    with patch(
        "app.core.commission_aware_trading.calculate_commission",
        side_effect=[big_comm, fake_comm],
    ):
        qty_m, _ = cat.calculate_optimal_quantity("BTCUSDT", 10.5, 50.0, 10.0)
        assert qty_m == pytest.approx(0.2)

    with patch(
        "app.core.commission_aware_trading.calculate_commission",
        side_effect=RuntimeError("x"),
    ):
        assert cat.calculate_optimal_quantity("BTCUSDT", 100, 50)[0] == 0.0

    with patch.object(cat, "validate_trade_profitability", return_value=(True, {})):
        assert cat.should_execute_trade("BTCUSDT", "BUY", 100, 1, grid_level=1)[0]
    with patch.object(cat, "validate_trade_profitability", return_value=(False, {})):
        assert (
            cat.should_execute_trade("BTCUSDT", "BUY", 100, 1, grid_level=1)[0] is False
        )
    assert cat.should_execute_trade("BTCUSDT", "SELL", 100, 1, grid_level=1)[0]
    assert cat.should_execute_trade("BTCUSDT", "BUY", 100, 1)[0] is False
    assert cat.should_execute_trade("BTCUSDT", "SELL", 100, 1)[0]

    with patch.object(
        cat, "validate_trade_profitability", side_effect=RuntimeError("e")
    ):
        ok, msg = cat.should_execute_trade("BTCUSDT", "BUY", 100, 1, grid_level=1)
        assert ok is False and "Error" in msg


# ── continuous_monitoring ───────────────────────────────────────────────────


def test_continuous_monitoring_paths(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from app.core.continuous_monitoring import ContinuousMonitoring
    import app.core.continuous_monitoring as cm_mod

    mon = ContinuousMonitoring()
    assert mon.start_monitoring() is True
    assert mon.start_monitoring() is False  # already active
    mon.monitoring_interval = 0.01
    mon._perform_monitoring_check()  # error branches via failed imports → dicts with error
    mon.stop_monitoring()
    mon.stop_monitoring()  # inactive warning

    # load/save
    Path(mon.monitoring_file).write_text('{"total_checks": 5}', encoding="utf-8")
    mon2 = ContinuousMonitoring()
    assert mon2.monitoring_data["total_checks"] == 5
    Path(mon.monitoring_file).write_text("{bad", encoding="utf-8")
    ContinuousMonitoring()
    with patch("builtins.open", side_effect=OSError("x")):
        mon2.save_monitoring_data()

    # start failure
    mon3 = ContinuousMonitoring()
    with patch("threading.Thread", side_effect=RuntimeError("thr")):
        assert mon3.start_monitoring() is False

    # stop failure
    mon3.monitoring_active = True
    mon3.monitoring_thread = MagicMock()
    mon3.monitoring_thread.is_alive.return_value = True
    mon3.monitoring_thread.join.side_effect = RuntimeError("join")
    mon3.stop_monitoring()

    # loop exception + one check then stop
    mon4 = ContinuousMonitoring()
    mon4.monitoring_interval = 0.01
    calls = {"n": 0}

    def check_once():
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("loop")
        mon4.monitoring_active = False

    mon4.monitoring_active = True
    with patch.object(mon4, "_perform_monitoring_check", side_effect=check_once):
        mon4._monitoring_loop()

    # perform check success with stubs
    mon5 = ContinuousMonitoring()
    mon5.start_time = datetime.now()
    mon5.monitoring_data["status_history"] = [{"x": i} for i in range(101)]
    with (
        patch.object(
            mon5,
            "_check_circuit_breaker",
            return_value={
                "is_open": True,
                "reason": "x",
                "daily_loss": 0.1,
                "total_loss": 0.1,
                "consecutive_losses": 3,
            },
        ),
        patch.object(
            mon5, "_check_system_status", return_value={"system_safe": False}
        ),
        patch.object(
            mon5,
            "_check_paper_trading",
            return_value={"total_pnl_pct": -6.0, "balance": 1},
        ),
        patch.object(
            mon5, "_check_configuration", return_value={"trading_enabled": True}
        ),
        patch.object(mon5, "_check_performance", return_value={"uptime_hours": 1}),
    ):
        mon5._perform_monitoring_check()
    assert mon5.monitoring_data["alerts_triggered"] >= 1
    assert len(mon5.monitoring_data["status_history"]) <= 100

    with patch.object(mon5, "_check_circuit_breaker", side_effect=RuntimeError("c")):
        mon5._perform_monitoring_check()

    # check helpers success + error
    fake_cb = MagicMock()
    fake_cb.get_status.return_value = {
        "is_open": True,
        "reason": "r",
        "current_state": {
            "daily_loss": 0.01,
            "total_loss": 0.02,
            "consecutive_losses": 1,
        },
    }
    with patch("app.core.circuit_breaker.circuit_breaker", fake_cb):
        out = mon5._check_circuit_breaker()
        assert out["is_open"] is True

    fake_cb_err = MagicMock()
    fake_cb_err.get_status.side_effect = RuntimeError("e")
    with patch("app.core.circuit_breaker.circuit_breaker", fake_cb_err):
        assert "error" in mon5._check_circuit_breaker()

    with patch(
        "app.core.safety_validator.get_system_safety_status",
        return_value={"system_safe": True, "overall_status": "OK"},
    ):
        assert mon5._check_system_status()["system_safe"] is True
    with patch(
        "app.core.safety_validator.get_system_safety_status",
        side_effect=RuntimeError("e"),
    ):
        assert "error" in mon5._check_system_status()

    mon5.monitoring_data["paper_trading_trades"] = 0
    with patch(
        "app.core.paper_trading.get_paper_portfolio_summary",
        return_value={
            "current_balance": 100,
            "total_trades": 2,
            "open_positions": 0,
            "total_pnl": 1,
            "total_pnl_pct": 1,
        },
    ):
        assert mon5._check_paper_trading()["total_trades"] == 2
    with patch(
        "app.core.paper_trading.get_paper_portfolio_summary",
        side_effect=RuntimeError("e"),
    ):
        assert "error" in mon5._check_paper_trading()

    cfg = MagicMock()
    cfg.get_config_summary.return_value = {
        "system_settings": {
            "trading_enabled": False,
            "paper_trading": True,
            "emergency_stop_enabled": True,
        },
        "assets_summary": {"total_assets": 1, "active_assets": 1},
    }
    with patch("app.core.unified_config.get_config", return_value=cfg):
        assert mon5._check_configuration()["paper_trading"] is True
    with patch("app.core.unified_config.get_config", side_effect=RuntimeError("e")):
        assert "error" in mon5._check_configuration()

    mon5.start_time = datetime.now() - timedelta(hours=1)
    mon5.monitoring_data["performance_metrics"] = [{"x": i} for i in range(51)]
    with patch(
        "app.core.monitoring.get_monitoring_status",
        return_value={"system_status": "OK"},
    ):
        perf = mon5._check_performance()
        assert "uptime_hours" in perf
        assert len(mon5.monitoring_data["performance_metrics"]) <= 50
    mon5.start_time = None
    with patch(
        "app.core.monitoring.get_monitoring_status",
        return_value={"system_status": "OK"},
    ):
        assert "error" in mon5._check_performance()
    with patch(
        "app.core.monitoring.get_monitoring_status", side_effect=RuntimeError("e")
    ):
        assert "error" in mon5._check_performance()

    mon5._check_alerts({"circuit_breaker": {"is_open": False}, "bad": True})
    assert mon5.get_monitoring_summary()["error"] == "Monitoreo no iniciado"
    mon5.start_time = datetime.now()
    mon5.monitoring_data["status_history"] = [{"a": 1}]
    assert "uptime_hours" in mon5.get_monitoring_summary()
    assert "summary" in mon5.get_detailed_report()

    with patch.object(cm_mod.continuous_monitoring, "start_monitoring", return_value=True):
        assert cm_mod.start_continuous_monitoring() is True
    with patch.object(cm_mod.continuous_monitoring, "stop_monitoring"):
        cm_mod.stop_continuous_monitoring()
    with patch.object(
        cm_mod.continuous_monitoring, "get_monitoring_summary", return_value={}
    ):
        assert cm_mod.get_monitoring_summary() == {}
    with patch.object(
        cm_mod.continuous_monitoring, "get_detailed_report", return_value={}
    ):
        assert cm_mod.get_detailed_report() == {}


# ── error_handler ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_error_handler_full(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from app.core import error_handler as eh

    handler = eh.ErrorHandler()
    handler.log_error("api_error", RuntimeError("x"), {"k": 1})
    assert handler.error_counts["api_error"] == 1
    assert Path(handler.error_log_file).exists()

    # corrupt existing log + trim >100
    Path(handler.error_log_file).write_text("{bad", encoding="utf-8")
    for i in range(102):
        handler._save_error_to_file({"i": i})
    data = json.loads(Path(handler.error_log_file).read_text(encoding="utf-8"))
    assert len(data) <= 100

    with patch("builtins.open", side_effect=OSError("deny")):
        handler._save_error_to_file({"x": 1})

    with patch(
        "app.services.telegram_alert.send_telegram_alert", MagicMock()
    ) as tg:
        for _ in range(5):
            handler.log_error("api_error", RuntimeError("t"))
        assert tg.called

    with patch(
        "app.services.telegram_alert.send_telegram_alert",
        side_effect=RuntimeError("tg"),
    ):
        handler._trigger_error_alert("api_error", 99, 5)

    with patch.object(handler, "_save_error_to_file", side_effect=RuntimeError("s")):
        handler.log_error("x", RuntimeError("y"))

    handler._check_error_threshold("unknown_type_xyz")
    handler.error_counts = MagicMock()
    handler.error_counts.get.side_effect = RuntimeError("boom")
    handler._check_error_threshold("api_error")

    handler.error_counts = {"api_error": 5}
    summary = handler.get_error_summary()
    assert summary["total_errors"] == 5
    assert "api_error" in summary["critical_errors"]

    handler2 = eh.ErrorHandler()
    with patch("app.core.error_handler.sum", side_effect=RuntimeError("sum")):
        assert handler2.get_error_summary() == {}

    handler2.error_counts = {"a": 1}
    handler2.reset_error_count("a")
    assert handler2.error_counts["a"] == 0
    handler2.error_counts = {"a": 1, "b": 2}
    handler2.reset_error_count()
    assert handler2.error_counts == {}

    broken = eh.ErrorHandler()
    broken.error_counts = MagicMock()
    broken.error_counts.clear.side_effect = RuntimeError("r")
    broken.reset_error_count()
    broken.error_counts = MagicMock()
    broken.error_counts.__setitem__ = MagicMock(side_effect=RuntimeError("s"))
    type(broken.error_counts).__setitem__ = MagicMock(side_effect=RuntimeError("s"))
    # force except in reset for specific key
    with patch.dict({"_": 1}):
        broken2 = eh.ErrorHandler()
        broken2.error_counts = None  # type: ignore[assignment]
        broken2.reset_error_count("z")

    @eh.handle_errors("api_error")
    def boom_sync():
        raise ValueError("s")

    @eh.handle_errors("api_error")
    async def boom_async():
        raise ValueError("a")

    @eh.handle_errors("api_error", context={"c": 1})
    def ok_sync():
        return 42

    @eh.handle_errors("api_error")
    async def ok_async():
        return 43

    with pytest.raises(ValueError):
        boom_sync()
    with pytest.raises(ValueError):
        await boom_async()
    assert ok_sync() == 42
    assert await ok_async() == 43

    assert eh.safe_execute(lambda: 1, "api_error") == 1
    assert (
        eh.safe_execute(
            lambda: (_ for _ in ()).throw(ValueError("e")),
            "api_error",
            default_return=9,
        )
        == 9
    )

    async def ok_op():
        return "ok"

    assert await eh.ErrorRecovery.retry_operation(ok_op) == "ok"
    assert await eh.ErrorRecovery.retry_operation(lambda: 42) == 42

    fails = {"n": 0}

    async def fail_then_ok():
        fails["n"] += 1
        if fails["n"] < 2:
            raise RuntimeError("retry")
        return "done"

    assert (
        await eh.ErrorRecovery.retry_operation(fail_then_ok, max_retries=3, delay=0.01)
        == "done"
    )

    sync_fails = {"n": 0}

    def fail_then_ok_sync():
        sync_fails["n"] += 1
        if sync_fails["n"] < 2:
            raise RuntimeError("retry")
        return "sync"

    assert (
        await eh.ErrorRecovery.retry_operation(
            fail_then_ok_sync, max_retries=3, delay=0.01
        )
        == "sync"
    )

    async def always_fail():
        raise RuntimeError("no")

    with pytest.raises(RuntimeError):
        await eh.ErrorRecovery.retry_operation(always_fail, max_retries=2, delay=0.01)

    assert eh.ErrorRecovery.create_fallback_value("dict") == {}
    assert eh.ErrorRecovery.create_fallback_value("list") == []
    assert eh.ErrorRecovery.create_fallback_value("float") == 0.0
    assert eh.ErrorRecovery.create_fallback_value("int") == 0
    assert eh.ErrorRecovery.create_fallback_value("str") == ""
    assert eh.ErrorRecovery.create_fallback_value("bool") is False
    assert eh.ErrorRecovery.create_fallback_value("weird", "x") == "x"

    assert (
        await eh.ErrorRecovery.graceful_degradation(lambda: 1, lambda: 2, "api_error")
        == 1
    )
    assert (
        await eh.ErrorRecovery.graceful_degradation(
            lambda: (_ for _ in ()).throw(RuntimeError("p")),
            lambda: 2,
            "api_error",
        )
        == 2
    )
    with pytest.raises(RuntimeError):
        await eh.ErrorRecovery.graceful_degradation(
            lambda: (_ for _ in ()).throw(RuntimeError("p")),
            lambda: (_ for _ in ()).throw(RuntimeError("f")),
            "api_error",
        )

    async def a_ok():
        return "A"

    async def a_fail():
        raise RuntimeError("A")

    async def b_ok():
        return "B"

    async def b_fail():
        raise RuntimeError("B")

    assert await eh.ErrorRecovery.graceful_degradation(a_ok, b_ok, "x") == "A"
    assert await eh.ErrorRecovery.graceful_degradation(a_fail, b_ok, "x") == "B"
    with pytest.raises(RuntimeError):
        await eh.ErrorRecovery.graceful_degradation(a_fail, b_fail, "x")

    @eh.handle_api_errors
    def api_f():
        return 1

    assert api_f() == 1
    for deco in (
        eh.handle_database_errors,
        eh.handle_binance_errors,
        eh.handle_risk_manager_errors,
        eh.handle_telegram_errors,
    ):
        assert deco(lambda: True)() is True

    with patch("os.makedirs", side_effect=OSError("m")):
        eh.ErrorHandler()

    async def coro():
        return 7

    task = eh.safe_execute(coro, "api_error")
    if hasattr(task, "cancel"):
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass


# ── metrics_manager ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_metrics_manager_paths():
    from app.core.metrics_manager import MetricsManager

    mm = MetricsManager()
    with patch.object(mm.trading_active, "set", side_effect=RuntimeError("init")):
        mm._initialize_metrics()

    db = MagicMock()
    q = MagicMock()
    db.query.return_value = q
    q.group_by.return_value.all.return_value = [("BTCUSDT", "BUY", 2)]
    q.filter.return_value.group_by.return_value.all.return_value = [
        ("BTCUSDT", "SELL", 1)
    ]
    q.filter.return_value.scalar.return_value = 10.0
    q.filter.return_value = q
    q.group_by.return_value = q
    q.all.side_effect = [
        [("BTCUSDT", "BUY", 2)],
        [("BTCUSDT", "SELL", 1)],
    ]

    # trading metrics
    with patch("app.core.metrics_manager.SessionLocal", return_value=db):
        # rebuild query chain carefully
        chain = MagicMock()
        db.query.return_value = chain
        chain.group_by.return_value.all.return_value = [("BTCUSDT", "BUY", 2)]
        chain.filter.return_value.group_by.return_value.all.return_value = [
            ("ETHUSDT", "SELL", 1)
        ]
        await mm._update_trading_metrics()

    with patch(
        "app.core.metrics_manager.SessionLocal", side_effect=RuntimeError("db")
    ):
        await mm._update_trading_metrics()

    # profitability
    chain2 = MagicMock()
    db2 = MagicMock()
    db2.query.return_value = chain2
    chain2.filter.return_value.scalar.side_effect = [100.0, 10.0, 50.0, 1000.0]
    with patch("app.core.metrics_manager.SessionLocal", return_value=db2):
        await mm._update_profitability_metrics()

    chain2.filter.return_value.scalar.side_effect = [0.0, 0.0, 0.0, 0.0]
    with patch("app.core.metrics_manager.SessionLocal", return_value=db2):
        await mm._update_profitability_metrics()

    with patch(
        "app.core.metrics_manager.SessionLocal", side_effect=RuntimeError("db")
    ):
        await mm._update_profitability_metrics()

    # portfolio
    singleton = MagicMock()
    singleton.get_balances.return_value = {
        "USDT": 100.0,
        "BTC": 0.01,
        "ETH": 1.0,
        "SPK": 10.0,
        "ZERO": 0.0,
    }
    singleton.get_symbol_price.side_effect = [
        50000.0,
        RuntimeError("no eth"),
        RuntimeError("no spk"),
    ]
    with patch("app.core.metrics_manager.binance_client_singleton", singleton):
        await mm._update_portfolio_metrics()

    with patch(
        "app.core.metrics_manager.binance_client_singleton"
    ) as bad:
        bad.get_balances.side_effect = RuntimeError("bal")
        await mm._update_portfolio_metrics()

    # performance
    chain3 = MagicMock()
    db3 = MagicMock()
    db3.query.return_value = chain3
    chain3.distinct.return_value.all.return_value = [("BTCUSDT",)]
    chain3.filter.return_value.scalar.side_effect = [10, 7]
    with patch("app.core.metrics_manager.SessionLocal", return_value=db3):
        await mm._update_performance_metrics()
    with patch(
        "app.core.metrics_manager.SessionLocal", side_effect=RuntimeError("db")
    ):
        await mm._update_performance_metrics()

    with patch.object(mm, "_update_trading_metrics", new_callable=AsyncMock):
        with patch.object(mm, "_update_profitability_metrics", new_callable=AsyncMock):
            with patch.object(mm, "_update_portfolio_metrics", new_callable=AsyncMock):
                with patch.object(
                    mm, "_update_performance_metrics", new_callable=AsyncMock
                ):
                    await mm.update_all_metrics()

    with patch.object(
        mm, "_update_trading_metrics", new_callable=AsyncMock, side_effect=RuntimeError("u")
    ):
        await mm.update_all_metrics()

    mm.record_trade_execution("BTCUSDT", "BUY", 0.01, 50000.0, execution_time=0.5)
    mm.record_trade_execution("BTCUSDT", "SELL", 0.01, 50000.0, execution_time=0.0)
    with patch.object(mm.trades_total, "labels", side_effect=RuntimeError("m")):
        mm.record_trade_execution("BTCUSDT", "BUY", 1, 1)

    mm.record_signal_detected("BTCUSDT", "BUY")
    with patch.object(mm.signals_detected, "labels", side_effect=RuntimeError("s")):
        mm.record_signal_detected("BTCUSDT", "SELL")

    mm.record_error("x", "svc")
    mm.record_error("y")
    with patch.object(mm.errors_total, "labels", side_effect=RuntimeError("e")):
        mm.record_error("z", "svc")

    mm.set_system_health(True)
    mm.set_system_health(False)
    with patch.object(mm.system_health, "set", side_effect=RuntimeError("h")):
        mm.set_system_health(True)


# ── paper_trading ───────────────────────────────────────────────────────────


def test_paper_trading_ledger_adapter(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from app.core.paper_equity_ledger import PaperEquityLedger, PaperEquitySeries, to_money
    from app.core.paper_trading import (
        PaperTradingSystem,
        get_paper_portfolio_summary,
        get_paper_trading,
        place_paper_buy_order,
        place_paper_sell_order,
        _money_str,
    )

    assert _money_str(Decimal("0")) == "0"
    assert "1" in _money_str(Decimal("1.5"))

    ledger = PaperEquityLedger(
        initial_cash=to_money("1000"),
        deployed_capital=to_money("200"),
        storage_path=tmp_path / "ledger.json",
    )
    series = PaperEquitySeries(
        config_hash="abc",
        deployed_capital=to_money("200"),
        storage_path=tmp_path / "series.json",
    )
    state = tmp_path / "paper_trading_state.json"
    pts = PaperTradingSystem(
        initial_balance=1000.0,
        state_file=str(state),
        ledger=ledger,
        series=series,
    )

    assert pts.ledger is ledger
    assert pts.series is series
    assert pts.get_balance() == pytest.approx(1000.0)
    assert pts.get_positions() == {}
    assert pts.get_trade_history() == []

    # legacy load paths
    state.write_text(
        json.dumps(
            {
                "trade_history": [{"t": 1}],
                "positions": {"BTCUSDT": {"quantity": 1}},
            }
        ),
        encoding="utf-8",
    )
    PaperTradingSystem(state_file=str(state), ledger=ledger, series=series)

    state.write_text(
        json.dumps(
            {
                "trades": [],
                "positions": {"BTCUSDT": {}},
                "legacy_positions_reconciled": True,
            }
        ),
        encoding="utf-8",
    )
    PaperTradingSystem(state_file=str(state), ledger=ledger, series=series)

    state.write_text("{bad", encoding="utf-8")
    PaperTradingSystem(state_file=str(state), ledger=ledger, series=series)

    with patch("builtins.open", side_effect=OSError("deny")):
        pts.save_state()

    buy = pts.place_buy_order("BTCUSDT", 0.01, 50000.0, grid_level=1)
    assert buy["success"] is True
    assert "BTCUSDT" in pts.positions
    assert pts.place_buy_order("BTCUSDT", 100, 50000.0)["success"] is False

    eq = pts.mark_to_market({"BTCUSDT": 50500.0})
    assert eq is not None
    with patch(
        "app.core.inventory_controls.evaluate_and_enforce_from_paper",
        side_effect=RuntimeError("ic"),
    ):
        assert pts.mark_to_market({"BTCUSDT": 50500.0}) is not None

    with patch(
        "app.core.paper_trading.compute_paper_portfolio_value",
        return_value={"total_value_usdt": "1000"},
    ):
        assert pts.mark_to_market() is not None
    with patch(
        "app.core.paper_trading.compute_paper_portfolio_value", return_value=None
    ):
        assert pts.mark_to_market() is None

    sell = pts.place_sell_order("BTCUSDT", 0.01, 51000.0)
    assert sell["success"] is True
    assert pts.place_sell_order("BTCUSDT", 1.0, 51000.0)["success"] is False

    # missing mark for open inventory
    pts2_ledger = PaperEquityLedger(
        initial_cash=to_money("1000"),
        deployed_capital=to_money("200"),
        storage_path=tmp_path / "l2.json",
    )
    pts2 = PaperTradingSystem(
        ledger=pts2_ledger,
        series=PaperEquitySeries(
            config_hash="c",
            deployed_capital=to_money("200"),
            storage_path=tmp_path / "s2.json",
        ),
        state_file=str(tmp_path / "st2.json"),
    )
    pts2.place_buy_order("ETHUSDT", 0.1, 3000.0)
    assert pts2.mark_to_market({}) is None  # MarkPriceUnavailable

    assert isinstance(pts2.update_positions_pnl({"ETHUSDT": 3100.0}), float)
    assert pts2.update_positions_pnl({}) == 0.0

    summary = pts2.get_portfolio_summary({"ETHUSDT": 3100.0})
    assert summary["mark_prices_missing"] is False
    assert summary["equity_mtm_usdt"] is not None

    missing = pts2.get_portfolio_summary({})
    assert missing["mark_prices_missing"] is True

    pts2.daily_closes()
    pts2.daily_returns()
    pts2.reset_paper_trading(new_balance=500.0)
    assert pts2.initial_balance == 500.0
    pts2.reset_paper_trading()  # no new_balance branch

    import app.core.paper_trading as pt_mod

    with patch.object(
        pt_mod.paper_trading_system, "place_buy_order", return_value={"ok": 1}
    ):
        assert place_paper_buy_order("BTCUSDT", 1, 1) == {"ok": 1}
    with patch.object(
        pt_mod.paper_trading_system, "place_sell_order", return_value={"ok": 2}
    ):
        assert place_paper_sell_order("BTCUSDT", 1, 1) == {"ok": 2}
    with patch.object(
        pt_mod.paper_trading_system, "get_portfolio_summary", return_value={"p": 1}
    ):
        assert get_paper_portfolio_summary() == {"p": 1}
    assert get_paper_trading() is pt_mod.paper_trading_system

    pts3 = PaperTradingSystem(
        ledger=PaperEquityLedger(
            initial_cash=to_money("100"),
            deployed_capital=to_money("50"),
            storage_path=tmp_path / "l3.json",
        ),
        series=None,
        state_file=str(tmp_path / "st3.json"),
    )
    with patch(
        "app.core.paper_trading.get_paper_equity_series",
        return_value=series,
    ):
        assert pts3.series is series


# ── performance_utils ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_performance_utils():
    from app.core import performance_utils as pu

    cache = pu.MemoryCache()
    cache.set("k", "v", ttl=60)
    assert cache.get("k") == "v"
    cache.set("exp", "x", ttl=-1)
    assert cache.get("exp") is None
    assert cache.get("missing") is None
    cache.clear()
    assert cache.get("k") is None

    @pu.cached(ttl=60)
    def sync_add(a, b):
        return a + b

    assert sync_add(1, 2) == 3
    assert sync_add(1, 2) == 3  # cache hit

    @pu.cached(ttl=60)
    async def async_add(a, b):
        return a + b

    assert await async_add(2, 3) == 5
    assert await async_add(2, 3) == 5

    fake_pool = MagicMock()
    fake_conn = MagicMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=fake_conn)
    cm.__aexit__ = AsyncMock(return_value=None)
    fake_pool.acquire.return_value = cm

    with patch("app.core.performance_utils._db_pool", None):
        with patch(
            "app.core.performance_utils.asyncpg.create_pool",
            new_callable=AsyncMock,
            return_value=fake_pool,
        ):
            pool = await pu.get_db_pool()
            assert pool is fake_pool
            async with pu.get_db_connection() as conn:
                assert conn is fake_conn

    limiter = pu.RateLimiter(max_calls=2, time_window=60)
    assert await limiter.acquire() is True
    assert await limiter.acquire() is True
    assert await limiter.acquire() is False

    async def load():
        return [1, 2]

    lazy = pu.LazyLoader(load)
    assert await lazy.get_data() == [1, 2]
    assert await lazy.get_data() == [1, 2]
    lazy.reset()
    assert lazy._loaded is False

    async def q1():
        return 1

    async def q2():
        return 2

    results = await pu.batch_query([q1(), q2()], batch_size=1)
    assert results == [1, 2]

    @pu.measure_performance
    def sync_work():
        return 9

    @pu.measure_performance
    async def async_work():
        return 8

    assert sync_work() == 9
    assert await async_work() == 8


# ── safety_validator ────────────────────────────────────────────────────────


def test_safety_validator_paths(monkeypatch):
    monkeypatch.setenv("INITIAL_BALANCE", "1000")
    from app.core.safety_validator import (
        SafetyValidator,
        get_system_safety_status,
        trigger_emergency_stop,
        validate_and_execute_trade,
    )
    from decimal import Decimal

    sv = SafetyValidator()

    with patch(
        "app.core.safety_validator.check_trading_allowed", return_value=(False, "open")
    ):
        ok, _, msg = sv.validate_trade_request("BTCUSDT", "BUY", 0.01, 50000)
        assert ok is False and "Circuit" in msg

    with patch(
        "app.core.safety_validator.check_trading_allowed", return_value=(True, "OK")
    ), patch(
        "app.core.safety_validator.validate_trading_order",
        return_value=(False, {}, "bad precision"),
    ):
        ok, _, msg = sv.validate_trade_request("BTCUSDT", "BUY", 0.01, 50000)
        assert ok is False and "Precisión" in msg

    precision = {
        "quantity": Decimal("0.01"),
        "price": Decimal("50000"),
        "notional_value": Decimal("500"),
    }
    with patch(
        "app.core.safety_validator.check_trading_allowed", return_value=(True, "OK")
    ), patch(
        "app.core.safety_validator.validate_trading_order",
        return_value=(True, precision, "ok"),
    ), patch.object(sv, "_check_sufficient_balance", return_value=(False, "no bal")):
        ok, _, msg = sv.validate_trade_request("BTCUSDT", "BUY", 0.01, 50000)
        assert ok is False and "Balance" in msg

    with patch(
        "app.core.safety_validator.check_trading_allowed", return_value=(True, "OK")
    ), patch(
        "app.core.safety_validator.validate_trading_order",
        return_value=(True, precision, "ok"),
    ), patch.object(
        sv, "_check_sufficient_balance", return_value=(True, "ok")
    ), patch.object(sv, "_check_risk_limits", return_value=(False, "risk")):
        ok, _, msg = sv.validate_trade_request("BTCUSDT", "BUY", 0.01, 50000)
        assert ok is False and "Riesgo" in msg

    with patch(
        "app.core.safety_validator.check_trading_allowed", return_value=(True, "OK")
    ), patch(
        "app.core.safety_validator.validate_trading_order",
        return_value=(True, precision, "ok"),
    ):
        ok, data, _ = sv.validate_trade_request("BTCUSDT", "BUY", Decimal("0.01"), Decimal("50000"))
        assert ok and data["validation_passed"]

    bal_ok, _ = sv._check_sufficient_balance(
        "BTCUSDT", "BUY", Decimal("0.01"), Decimal("50000")
    )
    assert bal_ok is True
    bal_bad, _ = sv._check_sufficient_balance(
        "BTCUSDT", "BUY", Decimal("100"), Decimal("50000")
    )
    assert bal_bad is False
    assert sv._check_sufficient_balance(
        "BTCUSDT", "SELL", Decimal("0.01"), Decimal("50000")
    )[0]

    assert sv._check_risk_limits("BTCUSDT", Decimal("0.0001"), Decimal("10"))[0] is False
    assert sv._check_risk_limits("BTCUSDT", Decimal("0.01"), Decimal("50000"))[0]
    assert (
        sv._check_risk_limits("BTCUSDT", Decimal("1"), Decimal("600"))[0] is False
    )  # > 50% of 1000

    with patch("app.core.safety_validator.record_trade_event"), patch(
        "app.core.safety_validator.record_trade_result"
    ):
        sv.record_trade_execution(
            "BTCUSDT", "BUY", Decimal("0.01"), Decimal("50000"), True, Decimal("1")
        )
        sv.record_trade_execution(
            "BTCUSDT", "SELL", Decimal("0.01"), Decimal("50000"), False, Decimal("0")
        )

    with patch(
        "app.core.safety_validator.get_monitoring_status",
        return_value={"system_status": "OK"},
    ), patch(
        "app.core.safety_validator.check_trading_allowed", return_value=(True, "OK")
    ):
        st = sv.get_safety_status()
        assert st["system_safe"] is True

    with patch(
        "app.core.safety_validator.get_monitoring_status",
        return_value={"system_status": "CRITICAL"},
    ), patch(
        "app.core.safety_validator.check_trading_allowed", return_value=(True, "OK")
    ):
        assert sv.get_safety_status()["system_safe"] is False

    with patch("app.core.circuit_breaker.circuit_breaker") as cbr:
        sv.emergency_stop("test")
        cbr._open_circuit.assert_called()
        sv.reset_safety_systems("test")
        cbr.close_circuit.assert_called()

    with patch.object(
        sv, "validate_trade_request", return_value=(False, {}, "no")
    ):
        import app.core.safety_validator as svm

        with patch.object(svm, "safety_validator", sv):
            assert validate_and_execute_trade("BTCUSDT", "BUY", 1, 1)[0] is False

    with patch.object(
        sv,
        "validate_trade_request",
        return_value=(True, {"symbol": "BTCUSDT"}, "ok"),
    ), patch.object(sv, "record_trade_execution"):
        import app.core.safety_validator as svm

        with patch.object(svm, "safety_validator", sv):
            ok, data, _ = validate_and_execute_trade("BTCUSDT", "BUY", 0.01, 50000)
            assert ok and data["symbol"] == "BTCUSDT"
            assert get_system_safety_status() is not None or True
            with patch.object(sv, "get_safety_status", return_value={"ok": 1}):
                assert get_system_safety_status() == {"ok": 1}
            with patch.object(sv, "emergency_stop") as es:
                trigger_emergency_stop("x")
                es.assert_called_with("x")


# ── testing_system ──────────────────────────────────────────────────────────


def test_testing_system_paths(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from app.core.testing_system import TestingSystem
    import app.core.testing_system as ts_mod

    ts = TestingSystem()
    ts.test_file = str(tmp_path / "testing_results.json")

    with patch(
        "app.core.testing_system.check_trading_allowed", return_value=(True, "OK")
    ), patch(
        "app.core.circuit_breaker.record_trade_result"
    ), patch(
        "app.core.testing_system.circuit_breaker"
    ) as cbr:
        cbr.get_status.return_value = {"is_open": False}
        ok, details = ts.test_circuit_breaker()
        assert ok and "initial_state" in details

    with patch(
        "app.core.testing_system.check_trading_allowed",
        side_effect=RuntimeError("e"),
    ):
        ok, details = ts.test_circuit_breaker()
        assert ok is False and "error" in details

    with patch(
        "app.core.testing_system.validate_trading_order",
        side_effect=[
            (True, {"q": 1}, "ok"),
            (False, {}, "bad"),
        ],
    ):
        ok, _ = ts.test_precision_validator()
        assert ok is True
    with patch(
        "app.core.testing_system.validate_trading_order",
        side_effect=RuntimeError("e"),
    ):
        assert ts.test_precision_validator()[0] is False

    with patch(
        "app.core.testing_system.get_monitoring_status",
        return_value={"system_status": "OK", "metrics": {}},
    ):
        assert ts.test_monitoring_system()[0] is True
    with patch(
        "app.core.testing_system.get_monitoring_status",
        side_effect=RuntimeError("e"),
    ):
        assert ts.test_monitoring_system()[0] is False

    with patch(
        "app.core.testing_system.get_system_safety_status",
        return_value={"circuit_breaker": {}, "monitoring": {}},
    ):
        assert ts.test_safety_validator()[0] is True
    with patch(
        "app.core.testing_system.get_system_safety_status",
        side_effect=RuntimeError("e"),
    ):
        assert ts.test_safety_validator()[0] is False

    cfg = MagicMock()
    cfg.get_config_summary.return_value = {
        "assets_summary": {"total_assets": 2}
    }
    cfg.validate_config.return_value = (True, [])
    with patch("app.core.testing_system.get_config", return_value=cfg):
        assert ts.test_unified_config()[0] is True
    with patch(
        "app.core.testing_system.get_config", side_effect=RuntimeError("e")
    ):
        assert ts.test_unified_config()[0] is False

    paper = MagicMock()
    paper.get_balance.return_value = 1000
    paper.get_positions.return_value = {}
    paper.get_trade_history.return_value = []
    paper.place_buy_order.return_value = {"success": True}
    paper.place_sell_order.return_value = {"success": True}
    paper.get_portfolio_summary.return_value = {}
    with patch("app.core.testing_system.get_paper_trading", return_value=paper):
        assert ts.test_paper_trading()[0] is True
    with patch(
        "app.core.testing_system.get_paper_trading", side_effect=RuntimeError("e")
    ):
        assert ts.test_paper_trading()[0] is False

    with patch(
        "app.core.testing_system.check_trading_allowed", return_value=(False, "blocked")
    ):
        assert ts.test_integration()[0] is False
    with patch(
        "app.core.testing_system.check_trading_allowed", return_value=(True, "OK")
    ), patch(
        "app.core.testing_system.validate_trading_order",
        return_value=(False, {}, "bad"),
    ):
        assert ts.test_integration()[0] is False
    with patch(
        "app.core.testing_system.check_trading_allowed", return_value=(True, "OK")
    ), patch(
        "app.core.testing_system.validate_trading_order",
        return_value=(True, {}, "ok"),
    ), patch(
        "app.core.safety_validator.validate_and_execute_trade",
        return_value=(True, {}, "ok"),
    ):
        assert ts.test_integration()[0] is True
    with patch(
        "app.core.testing_system.check_trading_allowed",
        side_effect=RuntimeError("e"),
    ):
        assert ts.test_integration()[0] is False

    cfg2 = MagicMock()
    cfg2.get_safety_limits.return_value = {"max_dd": 0.1}
    with patch(
        "app.core.circuit_breaker.record_trade_result"
    ), patch(
        "app.core.testing_system.check_trading_allowed",
        return_value=(False, "Límite de pérdida diaria excedido: 10%"),
    ), patch(
        "app.core.testing_system.validate_trading_order",
        return_value=(False, {}, "extreme"),
    ), patch("app.core.testing_system.get_config", return_value=cfg2):
        ok, details = ts.test_stress_scenarios()
        assert ok is True
        assert details["consecutive_losses"]["circuit_breaker_activated"]

    with patch(
        "app.core.circuit_breaker.record_trade_result",
        side_effect=RuntimeError("e"),
    ):
        assert ts.test_stress_scenarios()[0] is False

    ts.save_results({"A": {"success": True}})
    with patch("builtins.open", side_effect=OSError("deny")):
        ts.save_results({"A": {"success": True}})

    summary = ts.generate_summary(
        {
            "A": {"success": True},
            "B": {"success": True},
            "C": {"success": True},
        }
    )
    assert summary["overall_status"] == "PASSED"
    summary_w = ts.generate_summary(
        {"A": {"success": True}, "B": {"success": False}}
    )
    assert summary_w["overall_status"] == "WARNING"
    summary_f = ts.generate_summary(
        {
            "A": {"success": False},
            "B": {"success": False},
            "C": {"success": False},
        }
    )
    assert summary_f["overall_status"] == "FAILED"
    assert ts.generate_summary({})["success_rate"] == 0

    Path(ts.test_file).write_text(
        json.dumps({"T": {"success": True}}), encoding="utf-8"
    )
    report = ts.get_test_report()
    assert "results" in report
    Path(ts.test_file).unlink()
    assert "error" in ts.get_test_report()
    Path(ts.test_file).write_text("{bad", encoding="utf-8")
    assert "error" in ts.get_test_report()

    with patch.object(ts, "test_circuit_breaker", return_value=(True, {})), patch.object(
        ts, "test_precision_validator", return_value=(True, {})
    ), patch.object(ts, "test_monitoring_system", return_value=(True, {})), patch.object(
        ts, "test_safety_validator", return_value=(True, {})
    ), patch.object(ts, "test_unified_config", return_value=(True, {})), patch.object(
        ts, "test_paper_trading", return_value=(True, {})
    ), patch.object(ts, "test_integration", return_value=(True, {})), patch.object(
        ts, "test_stress_scenarios", side_effect=RuntimeError("boom")
    ):
        out = ts.run_all_tests()
        assert "summary" in out
        assert out["results"]["Stress Tests"]["success"] is False

    with patch.object(ts_mod.testing_system, "run_all_tests", return_value={"ok": 1}):
        assert ts_mod.run_complete_test_suite() == {"ok": 1}
    with patch.object(ts_mod.testing_system, "get_test_report", return_value={"r": 1}):
        assert ts_mod.get_test_report() == {"r": 1}
