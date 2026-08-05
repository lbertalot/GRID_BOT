"""Unit + contract tests for the ops reserve ledger (P0 slice S5, ADR-008).

Money is always Decimal. Enmienda CEO-01 (2026-08-05, Decisión 3): reserva
objetivo <= USD 100, devengo mensual de ~15 en vez de comprometer 150-250 de
golpe, y LLM pago excluido durante L0.

`ops_reserve_committed` es el número que el risk engine (Track A) resta al
capital aportado para obtener el capital tradable y el kill floor.
"""

import os
import sys
from datetime import date, datetime
from decimal import Decimal

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from fastapi.testclient import TestClient

from app.core.ops_ledger import (
    DEFAULT_OPS_ACCRUAL_START,
    DEFAULT_OPS_EXCLUDED_CATEGORIES,
    DEFAULT_OPS_MONTHLY_CAP_USD,
    DEFAULT_OPS_RESERVE_USD,
    OPS_CATEGORIES,
    CategoryExcludedError,
    InvalidAmountError,
    InvalidCategoryError,
    InvalidDateError,
    JsonOpsLedgerStore,
    OpsLedger,
    OpsLedgerError,
    compute_tradable_capital,
    get_ops_ledger,
)
from app.main import app


# Fecha del All Hands: mes 0 del devengo
NOW = datetime(2026, 8, 5, 12, 0, 0)
# Go-live enmendado (CEO-01, Decisión 2)
GO_LIVE = date(2026, 9, 15)
CONTRIBUTED = Decimal("1000")


@pytest.fixture
def ledger_path(tmp_path):
    return tmp_path / "ops_ledger.json"


@pytest.fixture
def ledger(ledger_path):
    """Ledger con los defaults post-enmienda: reserva 100, devengo/cap 15."""
    return OpsLedger(
        store=JsonOpsLedgerStore(ledger_path),
        reserve_usd=Decimal("100"),
        monthly_cap_usd=Decimal("15"),
        accrual_start=date(2026, 8, 5),
    )


# ─── Defaults de la enmienda CEO-01 ──────────────────────────────────────────


def test_amended_defaults():
    assert DEFAULT_OPS_RESERVE_USD == Decimal("100")
    assert DEFAULT_OPS_MONTHLY_CAP_USD == Decimal("10")  # CEO Acta 02
    assert DEFAULT_OPS_ACCRUAL_START == date(2026, 8, 5)
    assert DEFAULT_OPS_EXCLUDED_CATEGORIES == ("llm",)


# ─── Ledger vacío ────────────────────────────────────────────────────────────


def test_empty_ledger_summary(ledger):
    summary = ledger.summary(NOW)

    assert summary["ops_reserve_total"] == Decimal("100.00")
    assert summary["ops_burn_mtd"] == Decimal("0.00")
    assert summary["ops_burn_total"] == Decimal("0.00")
    assert summary["ops_reserve_remaining"] == Decimal("100.00")
    assert summary["monthly_cap"] == Decimal("15.00")
    assert summary["cap_exceeded"] is False
    assert summary["projected_annual_burn"] == Decimal("0.00")
    assert summary["reserve_exhausted_projection"] is False
    assert summary["entries_count"] == 0


def test_empty_ledger_has_no_entries(ledger):
    assert ledger.list_entries() == []


def test_missing_file_is_not_created_on_read(ledger, ledger_path):
    ledger.summary(NOW)
    assert not ledger_path.exists()


# ─── Una entrada ─────────────────────────────────────────────────────────────


def test_single_entry_updates_burn_and_remaining(ledger):
    ledger.add_entry(
        date="2026-08-03",
        category="vps",
        amount_usd=Decimal("12.50"),
        note="Hetzner CX22",
    )

    summary = ledger.summary(NOW)
    assert summary["ops_burn_mtd"] == Decimal("12.50")
    assert summary["ops_burn_total"] == Decimal("12.50")
    assert summary["ops_reserve_remaining"] == Decimal("87.50")
    assert summary["cap_exceeded"] is False
    assert summary["entries_count"] == 1


def test_entry_is_persisted_across_instances(ledger, ledger_path):
    ledger.add_entry(date="2026-08-03", category="data", amount_usd=Decimal("9.99"))

    reloaded = OpsLedger(
        store=JsonOpsLedgerStore(ledger_path),
        reserve_usd=Decimal("100"),
        monthly_cap_usd=Decimal("15"),
    )
    entries = reloaded.list_entries()
    assert len(entries) == 1
    assert entries[0].category == "data"
    assert entries[0].amount_usd == Decimal("9.99")
    assert isinstance(entries[0].amount_usd, Decimal)


def test_add_entry_accepts_date_objects(ledger):
    entry = ledger.add_entry(
        date=date(2026, 8, 4), category="data", amount_usd=Decimal("5")
    )
    assert entry.date == date(2026, 8, 4)
    assert entry.month == "2026-08"


# ─── Varios meses: MTD vs total ──────────────────────────────────────────────


def test_mtd_only_counts_current_month(ledger):
    ledger.add_entry(date="2026-06-10", category="vps", amount_usd=Decimal("12.00"))
    ledger.add_entry(date="2026-07-10", category="vps", amount_usd=Decimal("12.00"))
    ledger.add_entry(date="2026-08-01", category="vps", amount_usd=Decimal("8.00"))
    ledger.add_entry(date="2026-08-04", category="data", amount_usd=Decimal("3.00"))

    summary = ledger.summary(NOW)
    assert summary["ops_burn_mtd"] == Decimal("11.00")
    assert summary["ops_burn_total"] == Decimal("35.00")
    assert summary["ops_reserve_remaining"] == Decimal("65.00")
    assert summary["month"] == "2026-08"
    assert summary["months_observed"] == 3


def test_list_entries_filters_by_month_and_sorts_by_date(ledger):
    ledger.add_entry(date="2026-08-04", category="data", amount_usd=Decimal("8.00"))
    ledger.add_entry(date="2026-07-10", category="vps", amount_usd=Decimal("12.00"))
    ledger.add_entry(date="2026-08-01", category="vps", amount_usd=Decimal("12.00"))

    august = ledger.list_entries(month="2026-08")
    assert [e.date.isoformat() for e in august] == ["2026-08-01", "2026-08-04"]

    july = ledger.list_entries(month="2026-07")
    assert len(july) == 1

    assert ledger.list_entries(month="2026-09") == []


def test_list_entries_rejects_bad_month_format(ledger):
    with pytest.raises(InvalidDateError):
        ledger.list_entries(month="agosto-2026")


# ─── Validaciones ────────────────────────────────────────────────────────────


def test_invalid_category_is_rejected(ledger):
    with pytest.raises(InvalidCategoryError):
        ledger.add_entry(
            date="2026-08-03", category="marketing", amount_usd=Decimal("10")
        )
    assert ledger.list_entries() == []


def test_valid_categories_are_the_adr_set():
    assert set(OPS_CATEGORIES) == {"vps", "data", "llm", "other"}


@pytest.mark.parametrize("amount", [Decimal("0"), Decimal("0.00"), Decimal("-5.00")])
def test_non_positive_amount_is_rejected(ledger, amount):
    with pytest.raises(InvalidAmountError):
        ledger.add_entry(date="2026-08-03", category="vps", amount_usd=amount)
    assert ledger.list_entries() == []


def test_float_amount_is_rejected_financial_integrity(ledger):
    with pytest.raises(InvalidAmountError):
        ledger.add_entry(date="2026-08-03", category="vps", amount_usd=12.5)


def test_invalid_date_is_rejected(ledger):
    with pytest.raises(InvalidDateError):
        ledger.add_entry(date="05/08/2026", category="vps", amount_usd=Decimal("10"))


def test_errors_are_value_errors(ledger):
    assert issubclass(OpsLedgerError, ValueError)
    assert issubclass(InvalidCategoryError, OpsLedgerError)
    assert issubclass(InvalidAmountError, OpsLedgerError)
    assert issubclass(InvalidDateError, OpsLedgerError)
    assert issubclass(CategoryExcludedError, OpsLedgerError)


def test_negative_reserve_config_is_rejected(ledger_path):
    with pytest.raises(OpsLedgerError):
        OpsLedger(
            store=JsonOpsLedgerStore(ledger_path),
            reserve_usd=Decimal("-1"),
            monthly_cap_usd=Decimal("15"),
        )


# ─── Cap mensual (15 post-enmienda) ──────────────────────────────────────────


def test_cap_exceeded_when_month_burn_over_cap(ledger):
    ledger.add_entry(date="2026-08-01", category="vps", amount_usd=Decimal("10.00"))
    ledger.add_entry(date="2026-08-04", category="data", amount_usd=Decimal("8.00"))

    summary = ledger.summary(NOW)
    assert summary["ops_burn_mtd"] == Decimal("18.00")
    assert summary["cap_exceeded"] is True


def test_cap_not_exceeded_exactly_at_cap(ledger):
    ledger.add_entry(date="2026-08-01", category="vps", amount_usd=Decimal("15.00"))

    summary = ledger.summary(NOW)
    assert summary["ops_burn_mtd"] == Decimal("15.00")
    assert summary["cap_exceeded"] is False


def test_cap_of_previous_month_does_not_leak(ledger):
    ledger.add_entry(date="2026-07-15", category="vps", amount_usd=Decimal("90.00"))

    summary = ledger.summary(NOW)
    assert summary["ops_burn_mtd"] == Decimal("0.00")
    assert summary["cap_exceeded"] is False


# ─── Devengo mensual (CEO-01, Decisión 3) ────────────────────────────────────


def test_accrual_is_zero_at_program_start(ledger):
    summary = ledger.summary(NOW)
    assert summary["ops_accrual_months"] == 0
    assert summary["ops_accrued_to_date"] == Decimal("0.00")
    assert summary["ops_reserve_committed"] == Decimal("0.00")
    assert summary["ops_accrual_start"] == date(2026, 8, 5)
    assert summary["ops_monthly_accrual"] == Decimal("15.00")


def test_accrual_after_one_month(ledger):
    summary = ledger.summary(date(2026, 9, 5))
    assert summary["ops_accrual_months"] == 1
    assert summary["ops_accrued_to_date"] == Decimal("15.00")
    assert summary["ops_reserve_committed"] == Decimal("15.00")


def test_accrual_after_six_months(ledger):
    summary = ledger.summary(date(2027, 2, 5))
    assert summary["ops_accrual_months"] == 6
    assert summary["ops_accrued_to_date"] == Decimal("90.00")
    assert summary["ops_reserve_committed"] == Decimal("90.00")


def test_accrual_never_exceeds_reserve_total(ledger):
    # 12 x 15 = 180, pero el techo de la reserva es 100
    summary = ledger.summary(date(2027, 8, 5))
    assert summary["ops_accrual_months"] == 12
    assert summary["ops_accrued_to_date"] == Decimal("100.00")
    assert summary["ops_reserve_committed"] == Decimal("100.00")
    assert summary["ops_accrued_to_date"] <= summary["ops_reserve_total"]


def test_accrual_counts_only_completed_months(ledger):
    # 2026-09-04 todavía no completa el primer mes (inicio el día 5)
    assert ledger.summary(date(2026, 9, 4))["ops_accrual_months"] == 0
    assert ledger.summary(date(2026, 9, 5))["ops_accrual_months"] == 1


def test_accrual_is_zero_before_program_start(ledger):
    summary = ledger.summary(date(2026, 7, 1))
    assert summary["ops_accrual_months"] == 0
    assert summary["ops_reserve_committed"] == Decimal("0.00")


def test_accrual_is_deterministic_for_a_given_date(ledger):
    first = ledger.summary(date(2026, 11, 20))
    second = ledger.summary(datetime(2026, 11, 20, 23, 59))
    assert first["ops_accrued_to_date"] == second["ops_accrued_to_date"]
    assert first["ops_accrued_to_date"] == Decimal("45.00")


def test_accrual_at_go_live(ledger):
    # Go-live 2026-09-15: un mes devengado, no la reserva completa
    summary = ledger.summary(GO_LIVE)
    assert summary["ops_accrual_months"] == 1
    assert summary["ops_reserve_committed"] == Decimal("15.00")


# ─── Contrato con el risk engine (Track A) ───────────────────────────────────


def test_tradable_capital_at_month_one(ledger):
    committed = ledger.summary(date(2026, 9, 5))["ops_reserve_committed"]
    tradable = compute_tradable_capital(CONTRIBUTED, committed)
    assert tradable == Decimal("985.00")
    assert tradable.as_tuple().exponent == -2


def test_tradable_capital_at_month_six(ledger):
    committed = ledger.summary(date(2027, 2, 5))["ops_reserve_committed"]
    assert compute_tradable_capital(CONTRIBUTED, committed) == Decimal("910.00")


def test_ledger_exposes_tradable_capital_helper(ledger):
    assert ledger.tradable_capital(CONTRIBUTED, date(2026, 9, 5)) == Decimal("985.00")
    assert ledger.tradable_capital(CONTRIBUTED, date(2027, 2, 5)) == Decimal("910.00")


def test_tradable_capital_at_go_live(ledger):
    assert ledger.tradable_capital(CONTRIBUTED, GO_LIVE) == Decimal("985.00")


def test_kill_floor_derives_from_tradable_capital(ledger):
    # Track A: kill_floor = tradable_capital * 0.75 (CEO-01, Decisión 1)
    tradable = ledger.tradable_capital(CONTRIBUTED, GO_LIVE)
    assert (tradable * Decimal("0.75")).quantize(Decimal("0.01")) == Decimal("738.75")


def test_committed_follows_real_burn_when_it_exceeds_accrual(ledger):
    # Plata gastada de verdad: el risk engine no puede ver menos que el cash ido
    ledger.add_entry(date="2026-08-10", category="vps", amount_usd=Decimal("40.00"))

    summary = ledger.summary(date(2026, 9, 5))
    assert summary["ops_accrued_to_date"] == Decimal("15.00")
    assert summary["ops_reserve_committed"] == Decimal("40.00")
    assert summary["committed_driven_by_burn"] is True
    assert ledger.tradable_capital(CONTRIBUTED, date(2026, 9, 5)) == Decimal("960.00")


def test_committed_follows_accrual_when_burn_is_lower(ledger):
    ledger.add_entry(date="2026-08-10", category="vps", amount_usd=Decimal("5.00"))

    summary = ledger.summary(date(2026, 9, 5))
    assert summary["ops_reserve_committed"] == Decimal("15.00")
    assert summary["committed_driven_by_burn"] is False


def test_compute_tradable_capital_rejects_float():
    with pytest.raises(InvalidAmountError):
        compute_tradable_capital(1000.0, Decimal("15"))


# ─── LLM excluido en L0 (CEO-01, Decisión 3) ─────────────────────────────────


def test_llm_stays_in_the_enum(ledger):
    assert "llm" in OPS_CATEGORIES


def test_llm_entry_is_rejected_in_l0(ledger):
    with pytest.raises(CategoryExcludedError):
        ledger.add_entry(date="2026-08-03", category="llm", amount_usd=Decimal("10"))
    assert ledger.list_entries() == []


def test_llm_exclusion_is_not_an_invalid_category(ledger):
    # llm es válida como categoría; lo que vale cero es su presupuesto en L0
    with pytest.raises(CategoryExcludedError):
        ledger.add_entry(date="2026-08-03", category="llm", amount_usd=Decimal("10"))
    assert not issubclass(CategoryExcludedError, InvalidCategoryError)


def test_llm_budget_is_zero_in_summary(ledger):
    summary = ledger.summary(NOW)
    assert summary["excluded_categories"] == ("llm",)
    assert summary["category_budgets"]["llm"] == Decimal("0.00")
    assert summary["category_budgets"]["vps"] == Decimal("15.00")
    assert summary["excluded_category_burn"] == Decimal("0.00")
    assert summary["l0_policy_violation"] is False


def test_forced_llm_entry_flags_policy_violation(ledger):
    # Escape hatch de auditoría: si la plata se gastó, el ledger no debe mentir
    ledger.add_entry(
        date="2026-08-03",
        category="llm",
        amount_usd=Decimal("12.00"),
        note="LLM pago fuera de politica L0",
        allow_excluded=True,
    )

    summary = ledger.summary(NOW)
    assert summary["excluded_category_burn"] == Decimal("12.00")
    assert summary["l0_policy_violation"] is True
    assert summary["ops_burn_total"] == Decimal("12.00")


def test_llm_allowed_when_exclusion_is_lifted(ledger_path):
    post_l0 = OpsLedger(
        store=JsonOpsLedgerStore(ledger_path),
        reserve_usd=Decimal("100"),
        monthly_cap_usd=Decimal("15"),
        excluded_categories=(),
    )
    post_l0.add_entry(date="2026-08-03", category="llm", amount_usd=Decimal("10"))

    summary = post_l0.summary(NOW)
    assert summary["excluded_categories"] == ()
    assert summary["l0_policy_violation"] is False
    assert summary["category_budgets"]["llm"] == Decimal("15.00")


# ─── Proyección anual ────────────────────────────────────────────────────────


def test_projection_within_reserve_total(ledger):
    # 8/mes sostenidos → 96/año <= reserva de 100 → sin alerta
    ledger.add_entry(date="2026-06-10", category="vps", amount_usd=Decimal("8.00"))
    ledger.add_entry(date="2026-07-10", category="vps", amount_usd=Decimal("8.00"))
    ledger.add_entry(date="2026-08-01", category="vps", amount_usd=Decimal("8.00"))

    summary = ledger.summary(NOW)
    assert summary["projected_annual_burn"] == Decimal("96.00")
    assert summary["projected_annual_burn"] <= summary["ops_reserve_total"]
    assert summary["reserve_exhausted_projection"] is False


def test_projection_exhausts_reserve(ledger):
    # 12/mes sostenidos → 144/año > reserva de 100 → alerta (ADR-008 #4)
    ledger.add_entry(date="2026-06-10", category="vps", amount_usd=Decimal("12.00"))
    ledger.add_entry(date="2026-07-10", category="vps", amount_usd=Decimal("12.00"))
    ledger.add_entry(date="2026-08-01", category="vps", amount_usd=Decimal("12.00"))

    summary = ledger.summary(NOW)
    assert summary["months_observed"] == 3
    assert summary["projected_annual_burn"] == Decimal("144.00")
    assert summary["reserve_exhausted_projection"] is True


def test_spending_the_full_cap_every_month_exhausts_the_reserve(ledger):
    # Deja explícito que el cap de 15 es techo de mes malo, no objetivo:
    # 15 x 12 = 180 contra una reserva anual de 100
    ledger.add_entry(date="2026-07-10", category="vps", amount_usd=Decimal("15.00"))
    ledger.add_entry(date="2026-08-01", category="vps", amount_usd=Decimal("15.00"))

    summary = ledger.summary(NOW)
    assert summary["projected_annual_burn"] == Decimal("180.00")
    assert summary["reserve_exhausted_projection"] is True


def test_projection_counts_calendar_gaps(ledger):
    ledger.add_entry(date="2026-06-10", category="other", amount_usd=Decimal("30.00"))

    summary = ledger.summary(NOW)
    assert summary["months_observed"] == 3
    assert summary["projected_annual_burn"] == Decimal("120.00")


def test_overrun_leaves_negative_remaining(ledger):
    ledger.add_entry(date="2026-08-01", category="other", amount_usd=Decimal("120.00"))

    summary = ledger.summary(NOW)
    assert summary["ops_reserve_remaining"] == Decimal("-20.00")


# ─── Redondeo Decimal ────────────────────────────────────────────────────────


def test_amounts_are_quantized_to_two_decimals(ledger):
    entry = ledger.add_entry(
        date="2026-08-03", category="data", amount_usd=Decimal("10.005")
    )
    assert entry.amount_usd == Decimal("10.01")  # ROUND_HALF_UP

    ledger.add_entry(date="2026-08-03", category="data", amount_usd=Decimal("0.014"))
    summary = ledger.summary(NOW)
    assert summary["ops_burn_mtd"] == Decimal("10.02")
    assert summary["ops_burn_mtd"].as_tuple().exponent == -2


def test_dust_amount_rounding_to_zero_is_rejected(ledger):
    with pytest.raises(InvalidAmountError):
        ledger.add_entry(
            date="2026-08-03", category="data", amount_usd=Decimal("0.004")
        )


def test_projection_is_quantized_to_two_decimals(ledger):
    ledger.add_entry(date="2026-08-01", category="data", amount_usd=Decimal("10.01"))

    summary = ledger.summary(NOW)
    # 10.01 / 1 mes * 12 = 120.12
    assert summary["projected_annual_burn"] == Decimal("120.12")
    assert summary["projected_annual_burn"].as_tuple().exponent == -2


def test_accrual_is_quantized_to_two_decimals(ledger_path):
    odd = OpsLedger(
        store=JsonOpsLedgerStore(ledger_path),
        reserve_usd=Decimal("100"),
        monthly_cap_usd=Decimal("12.333"),
        accrual_start=date(2026, 8, 5),
    )
    summary = odd.summary(date(2026, 10, 5))
    assert summary["ops_monthly_accrual"] == Decimal("12.33")
    assert summary["ops_accrued_to_date"] == Decimal("24.66")
    assert summary["ops_accrued_to_date"].as_tuple().exponent == -2


def test_string_amounts_are_accepted_as_decimal(ledger):
    entry = ledger.add_entry(date="2026-08-03", category="vps", amount_usd="12.34")
    assert entry.amount_usd == Decimal("12.34")


# ─── Config por env ─────────────────────────────────────────────────────────


def test_env_defaults(monkeypatch, tmp_path):
    monkeypatch.delenv("OPS_RESERVE_USD", raising=False)
    monkeypatch.delenv("OPS_MONTHLY_CAP_USD", raising=False)
    monkeypatch.delenv("OPS_ACCRUAL_START", raising=False)
    monkeypatch.delenv("OPS_EXCLUDED_CATEGORIES", raising=False)
    monkeypatch.setenv("OPS_LEDGER_PATH", str(tmp_path / "ops.json"))

    summary = get_ops_ledger().summary(NOW)
    assert summary["ops_reserve_total"] == Decimal("100.00")
    assert summary["monthly_cap"] == Decimal("10.00")
    assert summary["ops_monthly_accrual"] == Decimal("10.00")
    assert summary["ops_accrual_start"] == date(2026, 8, 5)
    assert summary["excluded_categories"] == ("llm",)


def test_env_overrides(monkeypatch, tmp_path):
    monkeypatch.setenv("OPS_RESERVE_USD", "150")
    monkeypatch.setenv("OPS_MONTHLY_CAP_USD", "25.5")
    monkeypatch.setenv("OPS_ACCRUAL_START", "2026-09-01")
    monkeypatch.setenv("OPS_EXCLUDED_CATEGORIES", "llm,other")
    monkeypatch.setenv("OPS_LEDGER_PATH", str(tmp_path / "ops.json"))

    summary = get_ops_ledger().summary(NOW)
    assert summary["ops_reserve_total"] == Decimal("150.00")
    assert summary["monthly_cap"] == Decimal("25.50")
    assert summary["ops_accrual_start"] == date(2026, 9, 1)
    assert summary["excluded_categories"] == ("llm", "other")


def test_env_invalid_money_raises(monkeypatch, tmp_path):
    monkeypatch.setenv("OPS_RESERVE_USD", "cien")
    monkeypatch.setenv("OPS_LEDGER_PATH", str(tmp_path / "ops.json"))

    with pytest.raises(OpsLedgerError):
        get_ops_ledger()


def test_env_invalid_accrual_start_raises(monkeypatch, tmp_path):
    monkeypatch.setenv("OPS_ACCRUAL_START", "05/08/2026")
    monkeypatch.setenv("OPS_LEDGER_PATH", str(tmp_path / "ops.json"))

    with pytest.raises(OpsLedgerError):
        get_ops_ledger()


def test_env_invalid_excluded_category_raises(monkeypatch, tmp_path):
    monkeypatch.setenv("OPS_EXCLUDED_CATEGORIES", "marketing")
    monkeypatch.setenv("OPS_LEDGER_PATH", str(tmp_path / "ops.json"))

    with pytest.raises(OpsLedgerError):
        get_ops_ledger()


# ─── Contrato HTTP (Track C dashboard + Track A risk engine) ─────────────────

SUMMARY_KEYS = {
    # Reserva y devengo
    "ops_reserve_total",
    "ops_reserve_committed",
    "ops_accrued_to_date",
    "ops_monthly_accrual",
    "ops_accrual_start",
    "ops_accrual_months",
    "committed_driven_by_burn",
    # Gasto real
    "ops_burn_mtd",
    "ops_burn_total",
    "ops_reserve_remaining",
    "monthly_cap",
    "cap_exceeded",
    # Proyección
    "projected_annual_burn",
    "reserve_exhausted_projection",
    "months_observed",
    # Política L0
    "excluded_categories",
    "excluded_category_burn",
    "category_budgets",
    "l0_policy_violation",
    # Meta
    "month",
    "entries_count",
    "currency",
}


@pytest.fixture
def api_client(monkeypatch, tmp_path):
    monkeypatch.setenv("OPS_LEDGER_PATH", str(tmp_path / "ops_ledger.json"))
    monkeypatch.delenv("OPS_RESERVE_USD", raising=False)
    monkeypatch.delenv("OPS_MONTHLY_CAP_USD", raising=False)
    monkeypatch.delenv("OPS_ACCRUAL_START", raising=False)
    monkeypatch.delenv("OPS_EXCLUDED_CATEGORIES", raising=False)
    monkeypatch.setenv("API_KEY", "test-ops-key")
    return TestClient(app)


def test_get_summary_contract(api_client):
    response = api_client.get("/api/ops/summary")
    assert response.status_code == 200

    body = response.json()
    assert set(body) == SUMMARY_KEYS
    # Dinero como string decimal de 2 posiciones: el dashboard no debe ver floats
    assert body["ops_reserve_total"] == "100.00"
    assert body["monthly_cap"] == "10.00"
    assert body["ops_monthly_accrual"] == "10.00"
    assert body["ops_burn_mtd"] == "0.00"
    assert body["ops_reserve_remaining"] == "100.00"
    assert body["projected_annual_burn"] == "0.00"
    assert body["cap_exceeded"] is False
    assert body["reserve_exhausted_projection"] is False
    assert body["currency"] == "USD"
    assert body["entries_count"] == 0
    # Devengo: fecha ISO, meses como entero, committed como string decimal
    assert body["ops_accrual_start"] == "2026-08-05"
    assert isinstance(body["ops_accrual_months"], int)
    assert body["ops_reserve_committed"] == body["ops_accrued_to_date"]
    assert body["committed_driven_by_burn"] is False
    # Política L0
    assert body["excluded_categories"] == ["llm"]
    assert body["category_budgets"]["llm"] == "0.00"
    assert body["excluded_category_burn"] == "0.00"
    assert body["l0_policy_violation"] is False


def test_get_ledger_contract(api_client):
    response = api_client.get("/api/ops/ledger")
    assert response.status_code == 200

    body = response.json()
    assert body["count"] == 0
    assert body["entries"] == []
    assert body["currency"] == "USD"


def test_post_ledger_requires_auth(api_client):
    response = api_client.post(
        "/api/ops/ledger",
        json={"date": "2026-08-04", "category": "vps", "amount_usd": "12.50"},
    )
    assert response.status_code == 401


def test_post_ledger_appends_and_reflects_in_summary(api_client):
    response = api_client.post(
        "/api/ops/ledger",
        headers={"Authorization": "Bearer test-ops-key"},
        json={
            "date": "2026-08-04",
            "category": "vps",
            "amount_usd": "12.50",
            "note": "VPS mensual",
        },
    )
    assert response.status_code == 201
    assert response.json()["entry"] == {
        "date": "2026-08-04",
        "category": "vps",
        "amount_usd": "12.50",
        "note": "VPS mensual",
    }

    listed = api_client.get("/api/ops/ledger?month=2026-08").json()
    assert listed["count"] == 1
    assert listed["entries"][0]["amount_usd"] == "12.50"

    summary = api_client.get("/api/ops/summary").json()
    assert summary["ops_burn_total"] == "12.50"
    assert summary["ops_reserve_remaining"] == "87.50"


def test_post_ledger_rejects_invalid_category(api_client):
    response = api_client.post(
        "/api/ops/ledger",
        headers={"Authorization": "Bearer test-ops-key"},
        json={"date": "2026-08-04", "category": "marketing", "amount_usd": "12.50"},
    )
    assert response.status_code == 400


def test_post_ledger_rejects_llm_in_l0(api_client):
    response = api_client.post(
        "/api/ops/ledger",
        headers={"Authorization": "Bearer test-ops-key"},
        json={"date": "2026-08-04", "category": "llm", "amount_usd": "12.50"},
    )
    assert response.status_code == 400
    assert "llm" in response.json()["detail"]


def test_post_ledger_rejects_non_positive_amount(api_client):
    response = api_client.post(
        "/api/ops/ledger",
        headers={"Authorization": "Bearer test-ops-key"},
        json={"date": "2026-08-04", "category": "vps", "amount_usd": "0"},
    )
    assert response.status_code == 400


def test_get_ledger_rejects_bad_month(api_client):
    response = api_client.get("/api/ops/ledger?month=agosto")
    assert response.status_code == 422
