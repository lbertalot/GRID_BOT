"""Unit tests for the capital risk engine (P0 slice S2, ADR-003 + RISK_BLOCK fix).

Política vigente:
- Kill = -25% medido sobre `tradable_capital` (`KILL_BASIS=trading`, decisión CEO
  2026-08-05 que resuelve el RISK_BLOCK del Desk Lead).
- `dd_pool` (equity total vs aportado) se sigue calculando pero es **informativo**.
- Daily loss -3% vs equity EOD previo -> flat 24 h.
- Alerta -15%: se evalúa en ambas bases y se reporta cuál disparó.

Todo con Decimal y sin red (ni Binance ni Postgres/Redis).
"""

import json
import os
import sys
from decimal import Decimal

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from app.core.capital_risk import (
    ACTION_ALERT_DRAWDOWN,
    ACTION_DAILY_FLAT,
    ACTION_EMERGENCY_STOP,
    ACTION_KILL_LIQUIDATE,
    ACTION_REVIEW_OPS_BURN,
    BASIS_POOL,
    BASIS_TRADING,
    CapitalRiskConfig,
    CapitalRiskInputError,
    CapitalRiskStatus,
    EquitySnapshot,
    OpsSnapshot,
    apply_capital_risk_actions,
    build_breaker_port,
    daily_loss_pct,
    dd_vs_contributed,
    evaluate_capital_risk,
    kill_floor,
    resolve_equity_snapshot,
    resolve_ops_snapshot,
    tradable_capital,
)

# Config canónica de los tests: aportado 1.000, ops 200 comprometidos y gastados.
# Con esos números tradable = 800 y el kill floor de trading = 600.
NO_OPS = OpsSnapshot(
    reserve_committed=Decimal("0"),
    spent=Decimal("0"),
    source="test",
    assumed=False,
)


def _ops(committed: str, spent: str) -> OpsSnapshot:
    return OpsSnapshot(
        reserve_committed=Decimal(committed),
        spent=Decimal(spent),
        source="test",
        assumed=False,
    )


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #


def test_config_defaults_match_ceo_policy():
    cfg = CapitalRiskConfig.from_env(env={})
    assert cfg.contributed_capital == Decimal("1000")
    assert cfg.kill_drawdown_pct == Decimal("0.25")
    assert cfg.daily_loss_limit_pct == Decimal("0.03")
    assert cfg.alert_drawdown_pct == Decimal("0.15")
    assert cfg.ops_reserve_usd == Decimal("200")
    assert isinstance(cfg.contributed_capital, Decimal)


def test_kill_basis_defaults_to_trading():
    """Decisión CEO 2026-08-05: el kill mide pérdida de estrategia, no gasto de ops."""
    assert CapitalRiskConfig.from_env(env={}).kill_basis == BASIS_TRADING


@pytest.mark.parametrize("value,expected", [("pool", BASIS_POOL), ("TRADING", BASIS_TRADING)])
def test_kill_basis_from_env(value, expected):
    assert CapitalRiskConfig.from_env(env={"KILL_BASIS": value}).kill_basis == expected


@pytest.mark.parametrize("bad", ["hwm", "both", "0", "poool"])
def test_invalid_kill_basis_fails_closed(bad):
    with pytest.raises(CapitalRiskInputError) as exc:
        CapitalRiskConfig.from_env(env={"KILL_BASIS": bad})
    assert "KILL_BASIS" in str(exc.value)


def test_config_from_env_overrides():
    cfg = CapitalRiskConfig.from_env(
        env={
            "CONTRIBUTED_CAPITAL_USD": "2500.50",
            "KILL_DRAWDOWN_PCT": "0.20",
            "DAILY_LOSS_LIMIT_PCT": "0.02",
            "ALERT_DRAWDOWN_PCT": "0.10",
            "OPS_RESERVE_USD": "150",
            "KILL_BASIS": "pool",
        }
    )
    assert cfg.contributed_capital == Decimal("2500.50")
    assert cfg.kill_drawdown_pct == Decimal("0.20")
    assert cfg.daily_loss_limit_pct == Decimal("0.02")
    assert cfg.alert_drawdown_pct == Decimal("0.10")
    assert cfg.ops_reserve_usd == Decimal("150")
    assert cfg.kill_basis == BASIS_POOL


@pytest.mark.parametrize("bad", ["0", "-1000", "abc"])
def test_config_rejects_invalid_contributed_capital(bad):
    with pytest.raises(CapitalRiskInputError):
        CapitalRiskConfig.from_env(env={"CONTRIBUTED_CAPITAL_USD": bad})


def test_config_treats_empty_env_as_unset():
    """En Docker una var vacía es habitual; equivale a no seteada, no a error."""
    cfg = CapitalRiskConfig.from_env(env={"CONTRIBUTED_CAPITAL_USD": "", "KILL_BASIS": ""})
    assert cfg.contributed_capital == Decimal("1000")
    assert cfg.kill_basis == BASIS_TRADING


@pytest.mark.parametrize("bad", ["-0.1", "1.5", "abc"])
def test_config_rejects_invalid_kill_pct(bad):
    with pytest.raises(CapitalRiskInputError):
        CapitalRiskConfig.from_env(env={"KILL_DRAWDOWN_PCT": bad})


@pytest.mark.parametrize("bad", ["-1", "1000", "2000", "abc"])
def test_config_rejects_ops_reserve_that_leaves_no_tradable_capital(bad):
    with pytest.raises(CapitalRiskInputError):
        CapitalRiskConfig.from_env(env={"OPS_RESERVE_USD": bad})


# --------------------------------------------------------------------------- #
# Funciones puras
# --------------------------------------------------------------------------- #


def test_kill_floor_is_75pct_of_base():
    assert kill_floor(Decimal("1000")) == Decimal("750.00")
    assert kill_floor(Decimal("800")) == Decimal("600.00")


def test_kill_floor_custom_pct():
    assert kill_floor(Decimal("1000"), Decimal("0.20")) == Decimal("800.00")


@pytest.mark.parametrize("base", [Decimal("0"), Decimal("-1")])
def test_kill_floor_rejects_non_positive_base(base):
    with pytest.raises(CapitalRiskInputError):
        kill_floor(base)


@pytest.mark.parametrize(
    "committed,expected",
    [
        (Decimal("0"), Decimal("1000.00")),
        (Decimal("150"), Decimal("850.00")),
        (Decimal("200"), Decimal("800.00")),
        (Decimal("250"), Decimal("750.00")),
    ],
)
def test_tradable_capital(committed, expected):
    assert tradable_capital(Decimal("1000"), committed) == expected


@pytest.mark.parametrize("committed", [Decimal("-1"), Decimal("1000"), Decimal("1200")])
def test_tradable_capital_rejects_impossible_ops_reserve(committed):
    with pytest.raises(CapitalRiskInputError):
        tradable_capital(Decimal("1000"), committed)


@pytest.mark.parametrize(
    "equity,expected",
    [
        (Decimal("1000"), Decimal("0")),
        (Decimal("1100"), Decimal("0.10")),
        (Decimal("850"), Decimal("-0.15")),
        (Decimal("750"), Decimal("-0.25")),
        (Decimal("0"), Decimal("-1")),
    ],
)
def test_dd_vs_contributed(equity, expected):
    assert dd_vs_contributed(equity, Decimal("1000")) == expected


def test_dd_vs_contributed_rejects_zero_base():
    with pytest.raises(CapitalRiskInputError):
        dd_vs_contributed(Decimal("900"), Decimal("0"))


def test_dd_vs_contributed_rejects_missing_equity():
    with pytest.raises(CapitalRiskInputError):
        dd_vs_contributed(None, Decimal("1000"))


@pytest.mark.parametrize(
    "now,prev,expected",
    [
        (Decimal("1000"), Decimal("1000"), Decimal("0")),
        (Decimal("971"), Decimal("1000"), Decimal("-0.029")),
        (Decimal("970"), Decimal("1000"), Decimal("-0.03")),
        (Decimal("969"), Decimal("1000"), Decimal("-0.031")),
        (Decimal("1010"), Decimal("1000"), Decimal("0.01")),
    ],
)
def test_daily_loss_pct(now, prev, expected):
    assert daily_loss_pct(now, prev) == expected


@pytest.mark.parametrize("prev", [Decimal("0"), Decimal("-5"), None])
def test_daily_loss_pct_rejects_invalid_baseline(prev):
    with pytest.raises(CapitalRiskInputError):
        daily_loss_pct(Decimal("900"), prev)


def test_float_input_is_converted_without_binary_artifacts():
    # 0.1 + 0.2 en float es 0.30000000000000004; el engine normaliza via str()
    assert dd_vs_contributed(1100.10, 1000) == Decimal("0.1001")


# --------------------------------------------------------------------------- #
# Doble base: dd_pool (informativa) vs dd_trading (gobierna el kill)
# --------------------------------------------------------------------------- #


def test_both_bases_are_always_computed():
    st = evaluate_capital_risk(equity=Decimal("800"), ops=_ops("200", "200"))
    assert st.contributed_capital == Decimal("1000.00")
    assert st.tradable_capital == Decimal("800.00")
    assert st.equity_trading == Decimal("800.00")
    assert st.equity_pool == Decimal("800.00")  # ops ya gastado, no queda colchón
    assert st.dd_pool == Decimal("-0.20")
    assert st.dd_trading == Decimal("0")
    assert st.kill_floor_pool == Decimal("750.00")
    assert st.kill_floor_trading == Decimal("600.00")


def test_unspent_ops_reserve_counts_in_pool_equity():
    """Reserva comprometida pero no gastada sigue en el pool: dd_pool no la castiga."""
    st = evaluate_capital_risk(equity=Decimal("800"), ops=_ops("200", "0"))
    assert st.ops_remaining == Decimal("200.00")
    assert st.equity_pool == Decimal("1000.00")
    assert st.dd_pool == Decimal("0")
    assert st.dd_trading == Decimal("0")


@pytest.mark.parametrize(
    "committed,expected_tradable,expected_floor",
    [
        (Decimal("150"), Decimal("850.00"), Decimal("637.50")),
        (Decimal("250"), Decimal("750.00"), Decimal("562.50")),
    ],
)
def test_ops_reserve_moves_tradable_capital_and_trading_floor(
    committed, expected_tradable, expected_floor
):
    st = evaluate_capital_risk(
        equity=Decimal("800"), ops=_ops(str(committed), str(committed))
    )
    assert st.tradable_capital == expected_tradable
    assert st.kill_floor_trading == expected_floor
    assert st.kill_floor_pool == Decimal("750.00")  # la base pool no se mueve


# --------------------------------------------------------------------------- #
# RISK_BLOCK: gastar ops no es perder capital de trading
# --------------------------------------------------------------------------- #


def test_ops_burn_alone_does_not_kill_with_default_basis():
    """Equity 750 con 250 de ops gastados y P&L de trading 0: no es un kill."""
    st = evaluate_capital_risk(equity=Decimal("750"), ops=_ops("250", "250"))
    assert st.kill_basis == BASIS_TRADING
    assert st.kill_triggered is False
    assert st.kill_triggered_trading is False
    assert st.kill_triggered_pool is True
    assert st.kill_driven_by_ops_burn is True
    assert st.dd_trading == Decimal("0")
    assert st.dd_pool == Decimal("-0.25")
    assert ACTION_KILL_LIQUIDATE not in st.actions
    assert ACTION_REVIEW_OPS_BURN in st.actions
    assert any("ops" in reason.lower() for reason in st.reasons)


def test_ops_burn_kills_only_if_someone_forces_pool_basis():
    cfg = CapitalRiskConfig.from_env(env={"KILL_BASIS": "pool"})
    st = evaluate_capital_risk(
        equity=Decimal("750"), ops=_ops("250", "250"), config=cfg
    )
    assert st.kill_basis == BASIS_POOL
    assert st.kill_triggered is True
    assert st.kill_driven_by_ops_burn is True
    assert st.severity == "kill"
    assert ACTION_KILL_LIQUIDATE in st.actions
    assert ACTION_EMERGENCY_STOP in st.actions
    assert ACTION_REVIEW_OPS_BURN in st.actions


def test_real_trading_loss_kills_on_both_bases():
    """-25% sobre tradable (750 -> 562.50) es pérdida de estrategia, no gasto de ops."""
    st = evaluate_capital_risk(equity=Decimal("562.50"), ops=_ops("250", "250"))
    assert st.kill_triggered is True
    assert st.kill_triggered_trading is True
    assert st.kill_triggered_pool is True
    assert st.kill_driven_by_ops_burn is False
    assert st.dd_trading == Decimal("-0.25")
    assert st.severity == "kill"


def test_kill_reports_what_the_other_basis_would_say():
    st = evaluate_capital_risk(equity=Decimal("750"), ops=_ops("250", "250"))
    assert st.kill_basis == BASIS_TRADING
    assert st.kill_triggered_other_basis is True
    assert st.other_basis == BASIS_POOL


def test_trading_kill_border_is_inclusive():
    """Borde `<=`: equity exactamente en el floor de trading ya es kill."""
    at_floor = evaluate_capital_risk(equity=Decimal("600"), ops=_ops("200", "200"))
    above = evaluate_capital_risk(equity=Decimal("600.01"), ops=_ops("200", "200"))
    assert at_floor.kill_floor_trading == Decimal("600.00")
    assert at_floor.kill_triggered is True
    assert above.kill_triggered is False


def test_pool_kill_border_is_inclusive_when_basis_is_pool():
    cfg = CapitalRiskConfig.from_env(env={"KILL_BASIS": "pool"})
    at_floor = evaluate_capital_risk(equity=Decimal("750"), ops=NO_OPS, config=cfg)
    above = evaluate_capital_risk(equity=Decimal("750.01"), ops=NO_OPS, config=cfg)
    assert at_floor.kill_triggered is True
    assert above.kill_triggered is False


def test_without_ops_reserve_both_bases_coincide():
    st = evaluate_capital_risk(equity=Decimal("750"), ops=NO_OPS)
    assert st.tradable_capital == Decimal("1000.00")
    assert st.dd_pool == st.dd_trading == Decimal("-0.25")
    assert st.kill_triggered is True
    assert st.kill_driven_by_ops_burn is False


# --------------------------------------------------------------------------- #
# Alerta -15%: se evalúa en ambas bases y se reporta cuál disparó
# --------------------------------------------------------------------------- #


def test_alert_triggers_from_pool_base_even_if_trading_is_healthy():
    """Alerta CEO (KPI K3) vive en la base pool: es la que ve el capital aportado."""
    st = evaluate_capital_risk(equity=Decimal("850"), ops=_ops("200", "200"))
    assert st.dd_pool == Decimal("-0.15")
    assert st.dd_trading == Decimal("0.0625")
    assert st.alert_triggered is True
    assert st.alert_triggered_pool is True
    assert st.alert_triggered_trading is False
    assert st.alert_bases == [BASIS_POOL]
    assert ACTION_ALERT_DRAWDOWN in st.actions
    assert st.severity == "alert"


def test_alert_triggers_from_trading_base():
    st = evaluate_capital_risk(equity=Decimal("680"), ops=_ops("200", "0"))
    assert st.dd_trading == Decimal("-0.15")
    assert st.dd_pool == Decimal("-0.12")
    assert st.alert_triggered is True
    assert st.alert_triggered_trading is True
    assert st.alert_triggered_pool is False
    assert st.alert_bases == [BASIS_TRADING]


def test_alert_not_triggered_just_above_threshold():
    st = evaluate_capital_risk(equity=Decimal("850.01"), ops=_ops("200", "200"))
    assert st.alert_triggered is False
    assert st.alert_bases == []


# --------------------------------------------------------------------------- #
# Daily loss
# --------------------------------------------------------------------------- #


def test_healthy_equity_has_no_triggers():
    st = evaluate_capital_risk(
        equity=Decimal("980"), equity_prev_eod=Decimal("1000"), ops=_ops("200", "200")
    )
    assert st.kill_triggered is False
    assert st.alert_triggered is False
    assert st.daily_flat_triggered is False
    assert st.kill_driven_by_ops_burn is False
    assert st.actions == []
    assert st.reasons == []
    assert st.severity == "ok"
    assert st.daily_loss_pct == Decimal("-0.02")
    assert st.evaluated_at is not None


@pytest.mark.parametrize(
    "equity,expected_flat",
    [
        (Decimal("971"), False),  # -2.9%
        (Decimal("970"), True),  # -3.0% exacto -> flat
        (Decimal("969"), True),  # -3.1%
    ],
)
def test_daily_flat_threshold_border(equity, expected_flat):
    st = evaluate_capital_risk(
        equity=equity, equity_prev_eod=Decimal("1000"), ops=_ops("200", "200")
    )
    assert st.daily_flat_triggered is expected_flat
    if expected_flat:
        assert ACTION_DAILY_FLAT in st.actions
        assert st.severity == "daily_flat"


def test_daily_loss_basis_is_trading_equity():
    st = evaluate_capital_risk(
        equity=Decimal("970"), equity_prev_eod=Decimal("1000"), ops=_ops("200", "200")
    )
    assert st.daily_loss_basis == "trading_equity"


def test_missing_prev_eod_leaves_daily_loss_unevaluated():
    st = evaluate_capital_risk(equity=Decimal("900"), equity_prev_eod=None)
    assert st.daily_loss_pct is None
    assert st.daily_baseline_available is False
    assert st.daily_flat_triggered is False


def test_invalid_prev_eod_leaves_daily_loss_unevaluated_without_raising():
    """Un baseline corrupto no debe tumbar la evaluación del kill."""
    st = evaluate_capital_risk(
        equity=Decimal("500"), equity_prev_eod=Decimal("0"), ops=_ops("200", "200")
    )
    assert st.daily_loss_pct is None
    assert st.daily_baseline_available is False
    assert st.kill_triggered is True


def test_kill_and_daily_flat_can_coexist_with_kill_severity():
    st = evaluate_capital_risk(
        equity=Decimal("500"), equity_prev_eod=Decimal("1000"), ops=_ops("200", "200")
    )
    assert st.kill_triggered is True
    assert st.daily_flat_triggered is True
    assert st.severity == "kill"
    assert ACTION_KILL_LIQUIDATE in st.actions
    assert ACTION_DAILY_FLAT in st.actions


# --------------------------------------------------------------------------- #
# Inputs inválidos
# --------------------------------------------------------------------------- #


def test_missing_equity_raises_clear_error():
    with pytest.raises(CapitalRiskInputError) as exc:
        evaluate_capital_risk(equity=None)
    assert "equity" in str(exc.value).lower()


@pytest.mark.parametrize("contributed", [Decimal("0"), Decimal("-100")])
def test_invalid_contributed_capital_raises(contributed):
    cfg = CapitalRiskConfig(
        contributed_capital=contributed,
        kill_drawdown_pct=Decimal("0.25"),
        daily_loss_limit_pct=Decimal("0.03"),
        alert_drawdown_pct=Decimal("0.15"),
        ops_reserve_usd=Decimal("0"),
        kill_basis=BASIS_TRADING,
    )
    with pytest.raises(CapitalRiskInputError):
        evaluate_capital_risk(equity=Decimal("900"), config=cfg)


def test_ops_reserve_bigger_than_contributed_raises():
    with pytest.raises(CapitalRiskInputError):
        evaluate_capital_risk(equity=Decimal("900"), ops=_ops("1200", "0"))


def test_overspent_ops_is_flagged_and_clamped():
    """Gastar más que la reserva es un breach de Track B, no un crash del engine."""
    st = evaluate_capital_risk(equity=Decimal("700"), ops=_ops("200", "260"))
    assert st.ops_overspent is True
    assert st.ops_remaining == Decimal("0.00")
    assert st.equity_pool == Decimal("700.00")


# --------------------------------------------------------------------------- #
# Ops: parámetro de entrada, adaptador opcional (Track B) y supuesto por env
# --------------------------------------------------------------------------- #


def test_ops_defaults_to_env_reserve_and_is_flagged_as_assumed():
    """Sin ledger (Track B no está en este branch) el status declara el supuesto."""
    st = evaluate_capital_risk(equity=Decimal("800"))
    assert st.ops_reserve_committed == Decimal("200.00")
    assert st.ops_spent == Decimal("200.00")  # supuesto conservador: reserva gastada
    assert st.ops_assumed is True
    assert st.ops_source == "env_default"
    assert st.tradable_capital == Decimal("800.00")


def test_resolve_ops_snapshot_from_env():
    snap = resolve_ops_snapshot(
        env={"OPS_RESERVE_USD": "150", "OPS_SPENT_USD": "35.50"}, ledger=None
    )
    assert snap.reserve_committed == Decimal("150")
    assert snap.spent == Decimal("35.50")
    assert snap.assumed is False
    assert snap.source == "env"


def test_resolve_ops_snapshot_assumes_reserve_spent_when_unknown():
    snap = resolve_ops_snapshot(env={"OPS_RESERVE_USD": "150"}, ledger=None)
    assert snap.reserve_committed == Decimal("150")
    assert snap.spent == Decimal("150")
    assert snap.assumed is True
    assert snap.source == "env_default"


def test_resolve_ops_snapshot_uses_ledger_when_available():
    class _FakeOpsLedger:
        def get_ops_snapshot(self):
            return {
                "ops_reserve_committed_usd": "60",
                "ops_spent_usd": "35.50",
                "as_of": "2026-08-05T12:00:00+00:00",
            }

    snap = resolve_ops_snapshot(env={}, ledger=_FakeOpsLedger())
    assert snap.reserve_committed == Decimal("60")
    assert snap.spent == Decimal("35.50")
    assert snap.assumed is False
    assert snap.source == "ops_ledger"


def test_resolve_ops_snapshot_falls_back_when_ledger_breaks():
    class _BrokenLedger:
        def get_ops_snapshot(self):
            raise RuntimeError("ledger caído")

    snap = resolve_ops_snapshot(env={"OPS_RESERVE_USD": "200"}, ledger=_BrokenLedger())
    assert snap.reserve_committed == Decimal("200")
    assert snap.assumed is True
    assert snap.source == "env_default"


# --------------------------------------------------------------------------- #
# Serialización / contrato del dashboard
# --------------------------------------------------------------------------- #


def test_status_is_json_serializable_and_has_no_secrets():
    st = evaluate_capital_risk(
        equity=Decimal("800"), equity_prev_eod=Decimal("1000"), ops=_ops("200", "200")
    )
    payload = st.to_dict()
    dumped = json.dumps(payload)  # no debe explotar por Decimal/datetime
    assert "api_key" not in dumped.lower()
    assert "secret" not in dumped.lower()

    assert payload["contributed_capital"] == "1000.00"
    assert payload["tradable_capital"] == "800.00"
    assert payload["equity"] == "800.00"
    assert payload["kill_basis"] == "trading"
    assert payload["kill_floor"] == "600.00"  # floor de la base que gobierna
    assert payload["kill_triggered"] is False
    assert payload["dd_pool"] == "-0.200000"
    assert payload["dd_trading"] == "0.000000"
    assert payload["daily_loss_pct"] == "-0.200000"
    assert payload["daily_flat_triggered"] is True
    assert payload["severity"] == "daily_flat"

    assert payload["bases"]["trading"] == {
        "capital_base": "800.00",
        "equity": "800.00",
        "kill_floor": "600.00",
        "drawdown": "0.000000",
        "kill_triggered": False,
        "alert_triggered": False,
        "role": "kill",
    }
    assert payload["bases"]["pool"]["role"] == "informative"
    assert payload["bases"]["pool"]["kill_triggered"] is False

    assert payload["ops"] == {
        "reserve_committed": "200.00",
        "spent": "200.00",
        "remaining": "0.00",
        "overspent": False,
        "assumed": False,
        "source": "test",
    }
    assert payload["thresholds"]["kill_drawdown_pct"] == "0.25"
    assert payload["thresholds"]["daily_loss_limit_pct"] == "0.03"
    assert isinstance(payload["actions"], list)
    assert isinstance(payload["reasons"], list)


def test_status_dataclass_keeps_decimal_types():
    st = evaluate_capital_risk(equity=800.0, equity_prev_eod=1000.0)
    assert isinstance(st, CapitalRiskStatus)
    assert isinstance(st.equity, Decimal)
    assert isinstance(st.kill_floor, Decimal)
    assert isinstance(st.dd_pool, Decimal)
    assert isinstance(st.dd_trading, Decimal)
    assert isinstance(st.tradable_capital, Decimal)
    assert isinstance(st.daily_loss_pct, Decimal)


# --------------------------------------------------------------------------- #
# Enforcement paper-safe (puerto inyectable, sin efectos reales en tests)
# --------------------------------------------------------------------------- #


class _FakeBreakerPort:
    def __init__(self):
        self.emergency_calls = []
        self.disable_calls = []

    async def emergency_stop(self, reason: str) -> None:
        self.emergency_calls.append(reason)

    async def disable_trading(self, reason: str, duration_seconds: int) -> None:
        self.disable_calls.append((reason, duration_seconds))


async def test_apply_actions_noop_when_healthy():
    port = _FakeBreakerPort()
    st = evaluate_capital_risk(
        equity=Decimal("980"), equity_prev_eod=Decimal("1000"), ops=_ops("200", "200")
    )
    applied = await apply_capital_risk_actions(st, port)
    assert applied == []
    assert port.emergency_calls == []
    assert port.disable_calls == []


async def test_apply_actions_triggers_emergency_stop_on_kill():
    port = _FakeBreakerPort()
    st = evaluate_capital_risk(equity=Decimal("500"), ops=_ops("200", "200"))
    applied = await apply_capital_risk_actions(st, port)
    assert ACTION_EMERGENCY_STOP in applied
    assert len(port.emergency_calls) == 1
    assert "kill" in port.emergency_calls[0].lower()


async def test_apply_actions_does_not_stop_when_only_pool_base_breaches():
    """El falso positivo por ops no debe frenar el book con la base por defecto."""
    port = _FakeBreakerPort()
    st = evaluate_capital_risk(equity=Decimal("750"), ops=_ops("250", "250"))
    applied = await apply_capital_risk_actions(st, port)
    assert applied == []
    assert port.emergency_calls == []


async def test_apply_actions_mentions_ops_burn_when_kill_is_ops_driven():
    port = _FakeBreakerPort()
    cfg = CapitalRiskConfig.from_env(env={"KILL_BASIS": "pool"})
    st = evaluate_capital_risk(
        equity=Decimal("750"), ops=_ops("250", "250"), config=cfg
    )
    await apply_capital_risk_actions(st, port)
    assert "ops" in port.emergency_calls[0].lower()


async def test_apply_actions_disables_trading_24h_on_daily_flat():
    port = _FakeBreakerPort()
    st = evaluate_capital_risk(
        equity=Decimal("969"), equity_prev_eod=Decimal("1000"), ops=_ops("200", "200")
    )
    applied = await apply_capital_risk_actions(st, port)
    assert ACTION_DAILY_FLAT in applied
    assert port.disable_calls == [(port.disable_calls[0][0], 86400)]
    assert port.emergency_calls == []


async def test_apply_actions_requires_port():
    st = evaluate_capital_risk(equity=Decimal("500"), ops=_ops("200", "200"))
    with pytest.raises(CapitalRiskInputError):
        await apply_capital_risk_actions(st, None)


async def test_build_breaker_port_defaults_to_paper_safe_logger():
    """Sin adaptador de breakers (Track F no mergeado) no se ejecutan efectos."""
    port = build_breaker_port(None)
    st = evaluate_capital_risk(equity=Decimal("500"), ops=_ops("200", "200"))
    applied = await apply_capital_risk_actions(st, port)
    assert applied == [ACTION_EMERGENCY_STOP]


async def test_build_breaker_port_adapts_duck_typed_breakers():
    class _FakeBreakers:
        def __init__(self):
            self.critical = 0
            self.activated = []

        async def activate_critical_mode(self):
            self.critical += 1
            return True

        async def activate_breaker(self, breaker_type, reason=None):
            self.activated.append((breaker_type, reason))
            return True

    breakers = _FakeBreakers()
    port = build_breaker_port(breakers)
    st = evaluate_capital_risk(
        equity=Decimal("500"), equity_prev_eod=Decimal("1000"), ops=_ops("200", "200")
    )
    await apply_capital_risk_actions(st, port)
    assert breakers.critical == 1
    assert breakers.activated and breakers.activated[0][0] == "system_integrity"


# --------------------------------------------------------------------------- #
# Provider de equity (sin red, sin DB)
# --------------------------------------------------------------------------- #


def test_resolve_equity_from_env():
    snap = resolve_equity_snapshot(
        env={
            "CAPITAL_RISK_EQUITY_USD": "912.34",
            "CAPITAL_RISK_EQUITY_PREV_EOD_USD": "1000",
        },
        state_path="/does/not/exist.json",
    )
    assert snap.equity == Decimal("912.34")
    assert snap.equity_prev_eod == Decimal("1000")
    assert snap.source == "env"


def test_resolve_equity_from_paper_state_file(tmp_path):
    state = tmp_path / "paper_trading_state.json"
    state.write_text(json.dumps({"current_balance": 941.47, "equity_prev_eod": 1000.0}))
    snap = resolve_equity_snapshot(env={}, state_path=str(state))
    assert snap.equity == Decimal("941.47")
    assert snap.equity_prev_eod == Decimal("1000.0")
    assert snap.source == "paper_state"


def test_resolve_equity_unavailable_returns_none():
    snap = resolve_equity_snapshot(env={}, state_path="/does/not/exist.json")
    assert isinstance(snap, EquitySnapshot)
    assert snap.equity is None
    assert snap.source == "unavailable"


def test_resolve_equity_ignores_corrupt_state_file(tmp_path):
    state = tmp_path / "paper_trading_state.json"
    state.write_text("{not-json")
    snap = resolve_equity_snapshot(env={}, state_path=str(state))
    assert snap.equity is None
    assert snap.source == "unavailable"


# --------------------------------------------------------------------------- #
# Endpoint read-only
# --------------------------------------------------------------------------- #


def _client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.capital_risk_routes import router

    app = FastAPI()
    app.include_router(router)
    return app, TestClient(app)


def test_capital_status_endpoint_returns_both_bases(monkeypatch):
    monkeypatch.setenv("CAPITAL_RISK_EQUITY_USD", "800")
    monkeypatch.setenv("CAPITAL_RISK_EQUITY_PREV_EOD_USD", "1000")
    monkeypatch.setenv("OPS_RESERVE_USD", "200")
    monkeypatch.setenv("OPS_SPENT_USD", "200")
    monkeypatch.delenv("CONTRIBUTED_CAPITAL_USD", raising=False)
    monkeypatch.delenv("KILL_BASIS", raising=False)

    _, client = _client()
    resp = client.get("/api/risk/capital-status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    data = body["data"]
    assert data["equity"] == "800.00"
    assert data["kill_basis"] == "trading"
    assert data["kill_floor"] == "600.00"
    assert data["kill_triggered"] is False
    assert data["dd_pool"] == "-0.200000"
    assert data["dd_trading"] == "0.000000"
    assert data["bases"]["pool"]["role"] == "informative"
    assert data["bases"]["trading"]["role"] == "kill"
    assert data["equity_source"] == "env"
    assert data["ops"]["source"] == "env"
    assert "api_key" not in resp.text.lower()
    assert "secret" not in resp.text.lower()


def test_capital_status_endpoint_reports_ops_false_positive(monkeypatch):
    monkeypatch.setenv("CAPITAL_RISK_EQUITY_USD", "750")
    monkeypatch.setenv("OPS_RESERVE_USD", "250")
    monkeypatch.setenv("OPS_SPENT_USD", "250")
    monkeypatch.delenv("CAPITAL_RISK_EQUITY_PREV_EOD_USD", raising=False)
    monkeypatch.delenv("KILL_BASIS", raising=False)

    _, client = _client()
    data = client.get("/api/risk/capital-status").json()["data"]
    assert data["kill_triggered"] is False
    assert data["kill_driven_by_ops_burn"] is True
    assert data["bases"]["pool"]["kill_triggered"] is True
    assert data["daily_loss_pct"] is None


def test_capital_status_endpoint_reports_kill(monkeypatch):
    monkeypatch.setenv("CAPITAL_RISK_EQUITY_USD", "500")
    monkeypatch.setenv("OPS_RESERVE_USD", "200")
    monkeypatch.setenv("OPS_SPENT_USD", "200")
    monkeypatch.delenv("KILL_BASIS", raising=False)

    _, client = _client()
    data = client.get("/api/risk/capital-status").json()["data"]
    assert data["kill_triggered"] is True
    assert data["severity"] == "kill"


def test_capital_status_endpoint_fails_closed_without_equity(monkeypatch):
    monkeypatch.delenv("CAPITAL_RISK_EQUITY_USD", raising=False)
    monkeypatch.setenv("CAPITAL_RISK_STATE_PATH", "/does/not/exist.json")

    _, client = _client()
    resp = client.get("/api/risk/capital-status")
    assert resp.status_code == 503
    body = resp.json()
    assert body["success"] is False
    assert body["error"] == "equity_unavailable"
    assert body["data"] is None


def test_capital_status_endpoint_reports_config_error(monkeypatch):
    monkeypatch.setenv("CAPITAL_RISK_EQUITY_USD", "800")
    monkeypatch.setenv("KILL_BASIS", "hwm")

    _, client = _client()
    resp = client.get("/api/risk/capital-status")
    assert resp.status_code == 500
    assert resp.json()["error"] == "invalid_capital_risk_config"


def test_equity_provider_is_injectable(monkeypatch):
    """Seam para S6 (`app/core/capital_books.py`): se sobreescribe la dependencia."""
    from app.api.capital_risk_routes import get_equity_provider

    monkeypatch.delenv("CAPITAL_RISK_EQUITY_USD", raising=False)
    monkeypatch.setenv("CAPITAL_RISK_STATE_PATH", "/does/not/exist.json")

    app, client = _client()
    app.dependency_overrides[get_equity_provider] = lambda: (
        lambda: EquitySnapshot(
            equity=Decimal("910"), equity_prev_eod=Decimal("1000"), source="capital_books"
        )
    )
    data = client.get("/api/risk/capital-status").json()["data"]
    assert data["equity"] == "910.00"
    assert data["equity_source"] == "capital_books"


def test_ops_provider_is_injectable(monkeypatch):
    """Seam para Track B (`app/core/ops_ledger.py`)."""
    from app.api.capital_risk_routes import get_ops_provider

    monkeypatch.setenv("CAPITAL_RISK_EQUITY_USD", "800")
    monkeypatch.delenv("KILL_BASIS", raising=False)

    app, client = _client()
    app.dependency_overrides[get_ops_provider] = lambda: (
        lambda: OpsSnapshot(
            reserve_committed=Decimal("60"),
            spent=Decimal("35.50"),
            source="ops_ledger",
            assumed=False,
        )
    )
    data = client.get("/api/risk/capital-status").json()["data"]
    assert data["tradable_capital"] == "940.00"
    assert data["ops"]["source"] == "ops_ledger"
    assert data["ops"]["remaining"] == "24.50"


def test_route_is_registered_in_main_app():
    """Si el router no queda wired, el dashboard (ADR-005) se queda sin datos."""
    from app.main import app as main_app

    assert "/api/risk/capital-status" in {route.path for route in main_app.routes}


def test_orphan_risk_routes_stay_unregistered():
    """`risk_routes.py` expone POST /emergency-stop sin auth: no debe quedar wired."""
    from app.main import app as main_app

    paths = {route.path for route in main_app.routes}
    assert "/api/v2/risk/emergency-stop" not in paths
    assert "/api/v2/risk/status" not in paths
