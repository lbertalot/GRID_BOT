"""COV-70.A — ejecución paper: binance_service, broker, commission, precision, symbol filter.

Paper-only · mocks Binance/HTTP · Decimal · PROMOTE_LIVE: NO.
Cubre ramas residuales no ejercidas por test_cov_5_10 / test_cov_3_1 / test_cov_3_4.
"""

from __future__ import annotations

import json
import logging
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.precision_validator import (
    PrecisionValidator,
    get_symbol_precision_info,
    validate_trading_order,
)
from app.services.binance_service import (
    BinanceAPIException,
    BinanceService,
    Client,
)
from app.services.broker_market_execution import place_spot_market_via_adapter
from app.services.commission import (
    CommissionRates,
    calculate_commission,
    calculate_profit_with_commissions,
    get_default_commission_rates,
    update_commission_rates_from_binance,
    validate_minimum_profit,
)
from app.services.symbol_error_filter import (
    extract_symbol_from_error,
    filter_symbol_errors,
    validate_symbol_before_query,
)

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("paper_env")]


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def no_retry(monkeypatch):
    """Evita backoff de tenacity en paths de error (cero espera de red)."""
    monkeypatch.setattr(
        "app.services.binance_service.tenacity.retry",
        lambda **_kwargs: (lambda f: f),
    )


def _api_exc(code: int, message: str = "binance-error") -> BinanceAPIException:
    exc = BinanceAPIException(message)
    exc.code = code
    exc.message = message
    return exc


def _bare_svc(*, simulation: bool = True, force_real: bool = False) -> BinanceService:
    s = BinanceService.__new__(BinanceService)
    s.api_key = "k"
    s.api_secret = "s"
    s.simulation_mode = simulation
    s.force_real_mode = force_real
    s.client = MagicMock(name="binance_client")
    s.client.create_order.side_effect = AssertionError(
        "real create_order must not run under paper COV-70.A"
    )
    s._symbol_info_cache = {}
    s.redis_cache = AsyncMock()
    return s


# ── DummyClient (USE_REAL_BINANCE=0) ─────────────────────────────────────────


def test_dummy_client_paper_methods_no_network():
    client = Client(api_key="k", api_secret="s")
    assert client.get_account() == {"balances": []}
    bal = client.get_asset_balance("USDT")
    assert bal["asset"] == "USDT" and bal["free"] == "0"
    tick = client.get_symbol_ticker("ETHUSDT")
    assert tick["symbol"] == "ETHUSDT" and tick["price"] == "100.0"
    assert client.get_exchange_info() == {"symbols": []}
    assert client.order_market_buy(symbol="ETHUSDT", quantity="0.01")["status"] == "FILLED"
    assert client.order_market_sell(symbol="ETHUSDT", quantity="0.01")["orderId"] == 2
    assert client.order_limit_buy(symbol="ETHUSDT", quantity="0.01", price="2000")["status"] == "NEW"
    assert client.order_limit_sell(symbol="ETHUSDT", quantity="0.01", price="2100")["orderId"] == 4
    assert client.cancel_order(symbol="ETHUSDT", orderId=1)["status"] == "CANCELED"


# ── BinanceService.__init__ / _initialize_client ─────────────────────────────


def test_init_uses_singleton_when_ready(monkeypatch):
    singleton = MagicMock()
    singleton.is_ready.return_value = True
    singleton.client = MagicMock(name="ready_client")
    monkeypatch.setattr(
        "app.services.binance_client_singleton.get_binance_client_singleton",
        lambda: singleton,
    )
    with patch.object(BinanceService, "_initialize_client"):
        s = BinanceService()
    assert s.client is singleton.client
    assert s.simulation_mode is True


def test_init_fallback_when_singleton_not_ready_or_raises(monkeypatch):
    singleton = MagicMock()
    singleton.is_ready.return_value = False
    monkeypatch.setattr(
        "app.services.binance_client_singleton.get_binance_client_singleton",
        lambda: singleton,
    )
    with patch.object(BinanceService, "_initialize_client"):
        s = BinanceService()
    assert isinstance(s.client, Client)

    def _boom():
        raise RuntimeError("singleton down")

    monkeypatch.setattr(
        "app.services.binance_client_singleton.get_binance_client_singleton",
        _boom,
    )
    with patch.object(BinanceService, "_initialize_client"):
        s2 = BinanceService()
    assert isinstance(s2.client, Client)


def test_initialize_client_missing_creds_and_force_real():
    s = _bare_svc(simulation=False, force_real=True)
    s.api_key = ""
    s.api_secret = ""
    with pytest.raises(ValueError, match="FORCE_REAL_MODE"):
        s._initialize_client()

    s.force_real_mode = False
    s._initialize_client()
    assert s.simulation_mode is True


def test_initialize_client_account_success_and_api_errors():
    s = _bare_svc(simulation=False, force_real=False)
    mock_cli = MagicMock()
    mock_cli.get_account.return_value = {"accountType": "SPOT"}
    mock_cli.create_order.side_effect = AssertionError("no create_order")
    with patch("app.services.binance_service.Client", return_value=mock_cli):
        s._initialize_client()
    mock_cli.get_account.assert_called()

    mock_cli.get_account.side_effect = _api_exc(-2015, "IP/perms")
    s.simulation_mode = False
    with patch("app.services.binance_service.Client", return_value=mock_cli):
        s._initialize_client()
    assert s.simulation_mode is True

    mock_cli.get_account.side_effect = _api_exc(-1022, "sig")
    s.simulation_mode = False
    s.force_real_mode = False
    with patch("app.services.binance_service.Client", return_value=mock_cli):
        s._initialize_client()
    assert s.simulation_mode is True

    mock_cli.get_account.side_effect = _api_exc(-1022, "sig")
    s.simulation_mode = False
    s.force_real_mode = True
    with patch("app.services.binance_service.Client", return_value=mock_cli):
        with pytest.raises(BinanceAPIException):
            s._initialize_client()

    mock_cli.get_account.side_effect = _api_exc(-1000, "other")
    s.simulation_mode = False
    s.force_real_mode = False
    with patch("app.services.binance_service.Client", return_value=mock_cli):
        s._initialize_client()
    assert s.simulation_mode is True

    mock_cli.get_account.side_effect = _api_exc(-1000, "other")
    s.simulation_mode = False
    s.force_real_mode = True
    with patch("app.services.binance_service.Client", return_value=mock_cli):
        with pytest.raises(BinanceAPIException):
            s._initialize_client()

    mock_cli.get_account.side_effect = RuntimeError("unexpected")
    s.simulation_mode = False
    s.force_real_mode = False
    with patch("app.services.binance_service.Client", return_value=mock_cli):
        s._initialize_client()
    assert s.simulation_mode is True

    mock_cli.get_account.side_effect = RuntimeError("unexpected")
    s.simulation_mode = False
    s.force_real_mode = True
    with patch("app.services.binance_service.Client", return_value=mock_cli):
        with pytest.raises(RuntimeError, match="unexpected"):
            s._initialize_client()


def test_initialize_inner_api_error_not_2015_reraises_to_outer():
    s = _bare_svc(simulation=False, force_real=False)
    mock_cli = MagicMock()
    mock_cli.get_account.side_effect = _api_exc(-2014, "bad key")
    mock_cli.create_order.side_effect = AssertionError("no create_order")
    with patch("app.services.binance_service.Client", return_value=mock_cli):
        s._initialize_client()
    assert s.simulation_mode is True


# ── Real-mode reads (cliente mockeado, cero red) ─────────────────────────────


def test_account_balance_price_open_cancel_real_paths(no_retry):
    s = _bare_svc(simulation=False, force_real=True)
    s.client.get_account.return_value = {"accountType": "SPOT", "balances": []}
    s.client.get_asset_balance.return_value = {
        "asset": "USDT",
        "free": "250.00",
        "locked": "0",
    }
    s.client.get_symbol_ticker.return_value = {"symbol": "ETHUSDT", "price": "2500.5"}
    s.client.get_open_orders.return_value = [{"orderId": 11, "status": "NEW"}]
    s.client.cancel_order.return_value = {"orderId": 11, "status": "CANCELED"}

    acct = s.get_account_info()
    assert acct["accountType"] == "SPOT"
    bal = s.get_balance("USDT")
    assert Decimal(str(bal["free"])) == Decimal("250.00")
    assert s.get_current_price("ETHUSDT") == pytest.approx(2500.5)
    opens = s.get_open_orders("ETHUSDT")
    assert opens[0]["orderId"] == 11
    canceled = s.cancel_order("ETHUSDT", 11)
    assert canceled["status"] == "CANCELED"
    s.client.create_order.assert_not_called()

    s.client.get_account.side_effect = _api_exc(-1001, "acct")
    with pytest.raises(BinanceAPIException):
        s.get_account_info()
    s.client.get_asset_balance.side_effect = _api_exc(-1001, "bal")
    with pytest.raises(BinanceAPIException):
        s.get_balance("USDT")
    s.client.get_symbol_ticker.side_effect = _api_exc(-1001, "px")
    with pytest.raises(BinanceAPIException):
        s.get_current_price("ETHUSDT")
    s.client.get_open_orders.side_effect = _api_exc(-1001, "open")
    with pytest.raises(BinanceAPIException):
        s.get_open_orders("ETHUSDT")
    s.client.cancel_order.side_effect = _api_exc(-1001, "cx")
    with pytest.raises(BinanceAPIException):
        s.cancel_order("ETHUSDT", 1)


def test_adjust_quantity_exception_and_validate_edges(decimal_money):
    s = _bare_svc()
    with patch.object(
        s,
        "get_symbol_info",
        return_value={"stepSize": 0, "minQty": 0.001, "minNotional": 10.0},
    ):
        adj = s.adjust_quantity_precision(1.0, "ETHUSDT")
    assert "error" in adj
    assert adj["adjusted_quantity"] == 1.0

    qty_below = {
        "adjusted_quantity": 0.0001,
        "min_qty": 0.001,
        "min_notional": 10.0,
        "original_quantity": 0.0001,
    }
    with patch.object(s, "adjust_quantity_precision", return_value=qty_below), patch.object(
        s, "get_current_price", return_value=2000.0
    ), patch(
        "app.services.binance_service.commission_manager.calculate_commission",
        return_value=0.01,
    ):
        bad = s.validate_order_parameters("ETHUSDT", 0.0001, "BUY")
    assert bad["is_valid"] is False
    assert any("mínimo" in e.lower() or "minimo" in e.lower() for e in bad["errors"])

    with patch.object(s, "adjust_quantity_precision", side_effect=RuntimeError("adj")):
        err = s.validate_order_parameters("ETHUSDT", 1.0, "BUY")
    assert err["is_valid"] is False and err["quantity_info"] is None

    with patch(
        "app.services.binance_service.commission_manager.adjust_grid_levels_for_commissions",
        side_effect=RuntimeError("grid-math"),
    ):
        grid = s.validate_grid_profitability("ETHUSDT", 1900.0, 2100.0, 0.01, 2)
    assert grid["is_profitable"] is False
    assert grid["recommendation"] == "ERROR"


def test_execute_trading_order_real_paths_mocked_guard(decimal_money):
    """Ramas MARKET/LIMIT BUY/SELL con guard parcheado; create_order no se llama."""
    s = _bare_svc(simulation=False, force_real=True)
    s.client.get_symbol_info = MagicMock(return_value=None)
    s._symbol_info_cache["ETHUSDT"] = {
        "symbol": "ETHUSDT",
        "stepSize": 0.001,
        "minQty": 0.001,
        "minNotional": 10.0,
        "baseAsset": "ETH",
        "quoteAsset": "USDT",
        "pricePrecision": 2,
        "quantityPrecision": 3,
    }
    s.client.order_market_buy.return_value = {"orderId": 101, "status": "FILLED"}
    s.client.order_market_sell.return_value = {"orderId": 102, "status": "FILLED"}
    s.client.order_limit_buy.return_value = {"orderId": 103, "status": "NEW"}
    s.client.order_limit_sell.return_value = {"orderId": 104, "status": "NEW"}

    with patch(
        "app.core.order_execution_guard.assert_real_order_allowed",
        return_value={"effective_mode": "paper_test"},
    ), patch(
        "app.services.binance_service.commission_manager.calculate_commission",
        return_value=0.25,
    ):
        buy = s.execute_trading_order("ETHUSDT", "BUY", "MARKET", 0.01, price=2000.0)
        sell = s.execute_trading_order("ETHUSDT", "SELL", "MARKET", 0.01, price=2000.0)
        lb = s.execute_trading_order(
            "ETHUSDT", "BUY", "LIMIT", 0.01, price=1990.0
        )
        ls = s.execute_trading_order(
            "ETHUSDT", "SELL", "LIMIT", 0.01, price=2010.0
        )

    assert buy["orderId"] == 101
    assert Decimal(str(buy["commission_info"]["notional_value"])) == Decimal("20.00")
    assert sell["orderId"] == 102
    assert lb["status"] == "NEW" and ls["orderId"] == 104
    s.client.create_order.assert_not_called()
    s.client.order_market_buy.assert_called()
    s.client.order_limit_sell.assert_called()

    s.client.order_market_buy.side_effect = _api_exc(-2010, "insufficient")
    with patch(
        "app.core.order_execution_guard.assert_real_order_allowed",
        return_value={},
    ), patch(
        "app.services.binance_service.commission_manager.calculate_commission",
        return_value=0.0,
    ):
        with pytest.raises(BinanceAPIException):
            s.execute_trading_order("ETHUSDT", "BUY", "MARKET", 0.01, price=2000.0)


async def test_optimized_live_and_ticker_fallback():
    s = _bare_svc(simulation=False, force_real=True)
    s.redis_cache.get_account_info = AsyncMock(return_value=None)
    s.redis_cache.set_account_info = AsyncMock()
    with patch.object(s, "get_account", return_value={"accountType": "SPOT"}):
        acct = await s.get_account_optimized()
    assert acct["accountType"] == "SPOT"

    s.redis_cache.get_symbol_ticker = AsyncMock(return_value=None)
    s.redis_cache.set_symbol_ticker = AsyncMock()
    s.client.get_symbol_ticker.return_value = {
        "symbol": "ETHUSDT",
        "price": "1800.0",
    }
    tick = await s.get_symbol_ticker_optimized("ETHUSDT")
    assert tick["price"] == "1800.0"

    s.redis_cache.get_symbol_ticker = AsyncMock(side_effect=RuntimeError("redis"))
    s.get_symbol_ticker = MagicMock(return_value={"price": "1.0"})
    fb = await s.get_symbol_ticker_optimized("ETHUSDT")
    assert fb["price"] == "1.0"

    s.redis_cache.get_exchange_info = AsyncMock(return_value={"cached": True})
    cached = await s.get_exchange_info_optimized()
    assert cached["cached"] is True

    s.redis_cache.get_exchange_info = AsyncMock(return_value=None)
    s.redis_cache.set_exchange_info = AsyncMock()
    s.client.get_exchange_info.return_value = {"symbols": []}
    live_ex = await s.get_exchange_info_optimized()
    assert live_ex == {"symbols": []}
    s.redis_cache.set_exchange_info.assert_awaited()


# ── broker_market_execution ──────────────────────────────────────────────────


async def test_place_spot_market_via_adapter_validates_side_and_raw(decimal_money):
    with pytest.raises(ValueError, match="Lado inválido"):
        await place_spot_market_via_adapter(
            symbol="ETHUSDT", side="HOLD", quantity_base=0.01
        )

    ack = SimpleNamespace(raw={"orderId": 9, "status": "FILLED"})
    adapter = MagicMock()
    adapter.place_market_order = AsyncMock(return_value=ack)

    with patch(
        "app.core.order_execution_guard.assert_real_order_allowed",
        return_value={"effective_mode": "paper_test"},
    ), patch(
        "app.services.broker_market_execution.create_broker_adapter_from_env",
        return_value=adapter,
    ):
        out = await place_spot_market_via_adapter(
            symbol="ethusdt",
            side="buy",
            quantity_base=0.01,
            client_order_id="GRIDBOT_paper",
            recv_window_ms=5000,
        )
    assert out["orderId"] == 9
    req = adapter.place_market_order.await_args.args[0]
    assert req.symbol_code == "ETHUSDT"
    assert req.side == "BUY"
    assert req.quantity_base == decimal_money("0.01")

    ack_bad = SimpleNamespace(raw="not-a-dict")
    adapter.place_market_order = AsyncMock(return_value=ack_bad)
    with patch(
        "app.core.order_execution_guard.assert_real_order_allowed",
        return_value={},
    ), patch(
        "app.services.broker_market_execution.create_broker_adapter_from_env",
        return_value=adapter,
    ):
        with pytest.raises(TypeError, match="raw inválido"):
            await place_spot_market_via_adapter(
                symbol="ETHUSDT", side="SELL", quantity_base=0.02
            )


# ── commission (funciones puras) ─────────────────────────────────────────────


def test_commission_pure_math_and_validation(decimal_money):
    with pytest.raises(ValueError, match="positivo"):
        calculate_commission(decimal_money("0"), "MARKET")

    rates = CommissionRates(
        maker=decimal_money("0.0002"),
        taker=decimal_money("0.001"),
        symbol="ETHUSDT",
    )
    mkt = calculate_commission(decimal_money("1000"), "MARKET", rates)
    lim = calculate_commission(decimal_money("1000"), "LIMIT", rates)
    assert mkt.commission_usdt == decimal_money("1.00000000")
    assert lim.commission_usdt == decimal_money("0.20000000")
    assert mkt.commission_percentage == decimal_money("0.1")
    defaults = get_default_commission_rates()
    assert defaults.maker == decimal_money("0.001")

    with pytest.raises(ValueError, match="positivos"):
        calculate_profit_with_commissions(
            decimal_money("0"), decimal_money("110"), decimal_money("1")
        )

    profit = calculate_profit_with_commissions(
        decimal_money("100"),
        decimal_money("110"),
        decimal_money("1"),
        buy_order_type="MARKET",
        sell_order_type="LIMIT",
        commission_rates=rates,
    )
    assert profit["gross_profit"] == decimal_money("10")
    assert profit["net_profit"] < profit["gross_profit"]
    assert profit["buy_commission"] == decimal_money("0.10000000")
    assert profit["sell_commission"] == decimal_money("0.02200000")

    ok, data = validate_minimum_profit(
        decimal_money("100"),
        decimal_money("110"),
        decimal_money("1"),
        min_profit_percentage=decimal_money("0.5"),
        commission_rates=rates,
    )
    assert ok is True
    assert data["net_profit"] > 0

    bad, _ = validate_minimum_profit(
        decimal_money("100"),
        decimal_money("100.05"),
        decimal_money("1"),
        min_profit_percentage=decimal_money("5"),
        commission_rates=rates,
    )
    assert bad is False


async def test_update_commission_rates_from_binance_mocked():
    mock_cli = MagicMock()
    mock_cli.get_account.return_value = {
        "makerCommission": 10,
        "takerCommission": 20,
    }
    with patch("app.services.commission.Client", return_value=mock_cli):
        rates = await update_commission_rates_from_binance("k" * 32, "s" * 32)
    assert rates is not None
    assert rates.maker == Decimal("0.001")
    assert rates.taker == Decimal("0.002")

    with patch(
        "app.services.commission.Client", side_effect=RuntimeError("no-net")
    ):
        assert await update_commission_rates_from_binance("k", "s") is None


# ── precision_validator ──────────────────────────────────────────────────────


@pytest.fixture
def pv(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return PrecisionValidator()


def test_precision_cache_load_save_and_defaults(pv, tmp_path, decimal_money):
    cache = tmp_path / "precision_cache.json"
    cache.write_text(json.dumps({"FOOUSDT": {"quantity": 3, "price": 2, "step_size": 0.001}}))
    pv2 = PrecisionValidator()
    assert pv2.precision_cache["FOOUSDT"]["quantity"] == 3

    cache.write_text("{not-json")
    PrecisionValidator()  # except de load

    info = pv.get_symbol_precision("BNBUSDT")
    assert info["step_size"] == 0.0001
    unknown = pv.get_symbol_precision("XYZUSDT")
    assert unknown["quantity"] == 2
    ada = pv._get_default_precision("ADAUSDT")
    assert ada["step_size"] == 1

    with patch("builtins.open", side_effect=OSError("ro")):
        pv.save_precision_cache()


def test_precision_validate_quantity_price_order(pv, decimal_money):
    ok, qty, msg = pv.validate_quantity("BTCUSDT", decimal_money("0.00123"))
    assert ok is True and qty == decimal_money("0.00123")
    assert msg == "OK"

    ok_f, qty_f, _ = pv.validate_quantity("ETHUSDT", 0.01015)
    assert ok_f is True and qty_f == decimal_money("0.0101")

    bad, none, err = pv.validate_quantity("BTCUSDT", decimal_money("0"))
    assert bad is False and none is None and "mayor a 0" in err

    tiny, none2, err2 = pv.validate_quantity("BTCUSDT", decimal_money("0.000001"))
    assert tiny is False and none2 is None and "0 o negativa" in err2

    with patch.object(pv, "_is_valid_precision_format", return_value=False):
        inv, _, msg_inv = pv.validate_quantity("BTCUSDT", decimal_money("0.01"))
    assert inv is False and "precisión inválido" in msg_inv.lower()

    with patch.object(pv, "get_symbol_precision", side_effect=RuntimeError("cache")):
        fail, _, msg_f = pv.validate_quantity("BTCUSDT", decimal_money("1"))
    assert fail is False and "Error de validación" in msg_f

    zero_step = pv._adjust_to_step_size(decimal_money("1"), decimal_money("0"))
    assert zero_step == decimal_money("1")

    assert pv._is_valid_precision_format(decimal_money("12"), 0) is True
    broken = MagicMock()
    broken.normalize.side_effect = RuntimeError("norm")
    assert pv._is_valid_precision_format(broken, 2) is False

    pok, px, _ = pv.validate_price("BTCUSDT", 50123.456)
    assert pok is True and isinstance(px, Decimal)
    pbad, _, pmsg = pv.validate_price("ETHUSDT", decimal_money("0"))
    assert pbad is False and "mayor a 0" in pmsg
    with patch.object(pv, "get_symbol_precision", side_effect=RuntimeError("px")):
        perr, _, pem = pv.validate_price("ETHUSDT", decimal_money("10"))
    assert perr is False and "Error de validación" in pem

    qfail, data, qmsg = pv.validate_order("BTCUSDT", decimal_money("0"), decimal_money("50000"))
    assert qfail is False and data == {} and "cantidad" in qmsg.lower()

    pfail, _, pmsg2 = pv.validate_order(
        "BTCUSDT", decimal_money("0.001"), decimal_money("0")
    )
    assert pfail is False and "precio" in pmsg2.lower()

    vok, vdata, _ = pv.validate_order(
        "BTCUSDT", decimal_money("0.001"), decimal_money("50000")
    )
    assert vok is True
    assert vdata["notional_value"] == decimal_money("50.00000")

    low_n, _, nmsg = pv.validate_order(
        "BTCUSDT", decimal_money("0.00011"), decimal_money("100")
    )
    assert low_n is False and "notional" in nmsg.lower()

    summary = pv.get_validation_summary("HOMEUSDT")
    assert summary["symbol"] == "HOMEUSDT"
    assert summary["min_notional"] == 10.0

    with patch("app.core.precision_validator.precision_validator", pv):
        conv_ok, conv_data, _ = validate_trading_order("ETHUSDT", "0.01", "3000")
        info = get_symbol_precision_info("DOTUSDT")
    assert conv_ok is True
    assert conv_data["quantity"] == decimal_money("0.01")
    assert info["quantity_precision"] == 1


# ── symbol_error_filter ──────────────────────────────────────────────────────


def test_symbol_error_filter_validate_extract_and_dedupe():
    log = logging.getLogger("cov70.symbol_filter")
    assert validate_symbol_before_query("ETHUSDT", log) is True
    assert validate_symbol_before_query("FAKEUSDT", log) is False

    assert extract_symbol_from_error("Error para ETHUSDT en ticker") == "ETHUSDT"
    assert extract_symbol_from_error("sin par") == "UNKNOWN"

    log.filters.clear()
    filter_symbol_errors(log)
    filt = log.filters[-1]

    rec_ok = logging.LogRecord(
        "n", logging.INFO, __file__, 1, "heartbeat ok", (), None
    )
    assert filt.filter(rec_ok) is True

    rec1 = logging.LogRecord(
        "n",
        logging.WARNING,
        __file__,
        1,
        "Invalid symbol para ZZZUSDT",
        (),
        None,
    )
    rec2 = logging.LogRecord(
        "n",
        logging.WARNING,
        __file__,
        1,
        "Invalid symbol para ZZZUSDT",
        (),
        None,
    )
    rec_fb = logging.LogRecord(
        "n",
        logging.INFO,
        __file__,
        1,
        "usando fallback para ZZZUSDT",
        (),
        None,
    )
    with patch("app.services.symbol_error_filter.time.time", return_value=1_000.0):
        assert filt.filter(rec1) is True
        assert filt.filter(rec2) is False
        assert filt.filter(rec_fb) is False
    with patch("app.services.symbol_error_filter.time.time", return_value=1_070.0):
        rec3 = logging.LogRecord(
            "n",
            logging.WARNING,
            __file__,
            1,
            "Invalid symbol para ZZZUSDT",
            (),
            None,
        )
        assert filt.filter(rec3) is True
