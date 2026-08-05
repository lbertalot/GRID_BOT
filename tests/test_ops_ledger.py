"""Unit + contract tests for the ops reserve ledger (P0 slice S5, ADR-008).

Money is always Decimal: the ledger tracks the USD 150-250 ops reserve carved
out of the USD 1.000 seed, so it must never distort trading P&L.
"""

import os
import sys
from datetime import date, datetime
from decimal import Decimal

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from fastapi.testclient import TestClient

from app.core.ops_ledger import (
    OPS_CATEGORIES,
    InvalidAmountError,
    InvalidCategoryError,
    InvalidDateError,
    JsonOpsLedgerStore,
    OpsLedger,
    OpsLedgerError,
    get_ops_ledger,
)
from app.main import app


NOW = datetime(2026, 8, 5, 12, 0, 0)


@pytest.fixture
def ledger_path(tmp_path):
    return tmp_path / "ops_ledger.json"


@pytest.fixture
def ledger(ledger_path):
    return OpsLedger(
        store=JsonOpsLedgerStore(ledger_path),
        reserve_usd=Decimal("200"),
        monthly_cap_usd=Decimal("50"),
    )


# ─── Ledger vacío ────────────────────────────────────────────────────────────


def test_empty_ledger_summary(ledger):
    summary = ledger.summary(NOW)

    assert summary["ops_reserve_usd"] == Decimal("200.00")
    assert summary["ops_burn_mtd"] == Decimal("0.00")
    assert summary["ops_burn_total"] == Decimal("0.00")
    assert summary["ops_reserve_remaining"] == Decimal("200.00")
    assert summary["monthly_cap"] == Decimal("50.00")
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
    assert summary["ops_reserve_remaining"] == Decimal("187.50")
    assert summary["cap_exceeded"] is False
    assert summary["entries_count"] == 1


def test_entry_is_persisted_across_instances(ledger, ledger_path):
    ledger.add_entry(date="2026-08-03", category="llm", amount_usd=Decimal("9.99"))

    reloaded = OpsLedger(
        store=JsonOpsLedgerStore(ledger_path),
        reserve_usd=Decimal("200"),
        monthly_cap_usd=Decimal("50"),
    )
    entries = reloaded.list_entries()
    assert len(entries) == 1
    assert entries[0].category == "llm"
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
    ledger.add_entry(date="2026-08-01", category="vps", amount_usd=Decimal("12.00"))
    ledger.add_entry(date="2026-08-04", category="llm", amount_usd=Decimal("8.00"))

    summary = ledger.summary(NOW)
    assert summary["ops_burn_mtd"] == Decimal("20.00")
    assert summary["ops_burn_total"] == Decimal("44.00")
    assert summary["ops_reserve_remaining"] == Decimal("156.00")
    assert summary["month"] == "2026-08"
    assert summary["months_observed"] == 3


def test_list_entries_filters_by_month_and_sorts_by_date(ledger):
    ledger.add_entry(date="2026-08-04", category="llm", amount_usd=Decimal("8.00"))
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


def test_negative_reserve_config_is_rejected(ledger_path):
    with pytest.raises(OpsLedgerError):
        OpsLedger(
            store=JsonOpsLedgerStore(ledger_path),
            reserve_usd=Decimal("-1"),
            monthly_cap_usd=Decimal("50"),
        )


# ─── Cap mensual ─────────────────────────────────────────────────────────────


def test_cap_exceeded_when_month_burn_over_cap(ledger):
    ledger.add_entry(date="2026-08-01", category="llm", amount_usd=Decimal("30.00"))
    ledger.add_entry(date="2026-08-04", category="data", amount_usd=Decimal("25.00"))

    summary = ledger.summary(NOW)
    assert summary["ops_burn_mtd"] == Decimal("55.00")
    assert summary["cap_exceeded"] is True


def test_cap_not_exceeded_exactly_at_cap(ledger):
    ledger.add_entry(date="2026-08-01", category="llm", amount_usd=Decimal("50.00"))

    summary = ledger.summary(NOW)
    assert summary["ops_burn_mtd"] == Decimal("50.00")
    assert summary["cap_exceeded"] is False


def test_cap_of_previous_month_does_not_leak(ledger):
    ledger.add_entry(date="2026-07-15", category="llm", amount_usd=Decimal("90.00"))

    summary = ledger.summary(NOW)
    assert summary["ops_burn_mtd"] == Decimal("0.00")
    assert summary["cap_exceeded"] is False


# ─── Proyección anual ────────────────────────────────────────────────────────


def test_projection_exhausts_reserve(ledger):
    # 40 USD/mes sostenidos → 480/año > reserva de 200 → alerta (ADR-008 #4)
    ledger.add_entry(date="2026-06-10", category="vps", amount_usd=Decimal("40.00"))
    ledger.add_entry(date="2026-07-10", category="vps", amount_usd=Decimal("40.00"))
    ledger.add_entry(date="2026-08-01", category="vps", amount_usd=Decimal("40.00"))

    summary = ledger.summary(NOW)
    assert summary["months_observed"] == 3
    assert summary["projected_annual_burn"] == Decimal("480.00")
    assert summary["reserve_exhausted_projection"] is True


def test_projection_within_reserve(ledger):
    # 10 USD/mes → 120/año < reserva de 200 → sin alerta
    ledger.add_entry(date="2026-06-10", category="data", amount_usd=Decimal("10.00"))
    ledger.add_entry(date="2026-07-10", category="data", amount_usd=Decimal("10.00"))
    ledger.add_entry(date="2026-08-01", category="data", amount_usd=Decimal("10.00"))

    summary = ledger.summary(NOW)
    assert summary["projected_annual_burn"] == Decimal("120.00")
    assert summary["reserve_exhausted_projection"] is False


def test_projection_counts_calendar_gaps(ledger):
    # Un solo gasto en junio, hoy es agosto → 3 meses observados, no 1
    ledger.add_entry(date="2026-06-10", category="other", amount_usd=Decimal("30.00"))

    summary = ledger.summary(NOW)
    assert summary["months_observed"] == 3
    assert summary["projected_annual_burn"] == Decimal("120.00")


def test_overrun_leaves_negative_remaining(ledger):
    ledger.add_entry(date="2026-08-01", category="other", amount_usd=Decimal("250.00"))

    summary = ledger.summary(NOW)
    assert summary["ops_reserve_remaining"] == Decimal("-50.00")


# ─── Redondeo Decimal ────────────────────────────────────────────────────────


def test_amounts_are_quantized_to_two_decimals(ledger):
    entry = ledger.add_entry(
        date="2026-08-03", category="llm", amount_usd=Decimal("10.005")
    )
    assert entry.amount_usd == Decimal("10.01")  # ROUND_HALF_UP

    ledger.add_entry(date="2026-08-03", category="llm", amount_usd=Decimal("0.014"))
    summary = ledger.summary(NOW)
    assert summary["ops_burn_mtd"] == Decimal("10.02")
    assert summary["ops_burn_mtd"].as_tuple().exponent == -2


def test_dust_amount_rounding_to_zero_is_rejected(ledger):
    with pytest.raises(InvalidAmountError):
        ledger.add_entry(
            date="2026-08-03", category="llm", amount_usd=Decimal("0.004")
        )


def test_projection_is_quantized_to_two_decimals(ledger):
    ledger.add_entry(date="2026-08-01", category="llm", amount_usd=Decimal("10.01"))

    summary = ledger.summary(NOW)
    # 10.01 / 1 mes * 12 = 120.12
    assert summary["projected_annual_burn"] == Decimal("120.12")
    assert summary["projected_annual_burn"].as_tuple().exponent == -2


def test_string_amounts_are_accepted_as_decimal(ledger):
    entry = ledger.add_entry(date="2026-08-03", category="vps", amount_usd="12.34")
    assert entry.amount_usd == Decimal("12.34")


# ─── Config por env ─────────────────────────────────────────────────────────


def test_env_defaults(monkeypatch, tmp_path):
    monkeypatch.delenv("OPS_RESERVE_USD", raising=False)
    monkeypatch.delenv("OPS_MONTHLY_CAP_USD", raising=False)
    monkeypatch.setenv("OPS_LEDGER_PATH", str(tmp_path / "ops.json"))

    summary = get_ops_ledger().summary(NOW)
    assert summary["ops_reserve_usd"] == Decimal("200.00")
    assert summary["monthly_cap"] == Decimal("50.00")


def test_env_overrides(monkeypatch, tmp_path):
    monkeypatch.setenv("OPS_RESERVE_USD", "150")
    monkeypatch.setenv("OPS_MONTHLY_CAP_USD", "25.5")
    monkeypatch.setenv("OPS_LEDGER_PATH", str(tmp_path / "ops.json"))

    summary = get_ops_ledger().summary(NOW)
    assert summary["ops_reserve_usd"] == Decimal("150.00")
    assert summary["monthly_cap"] == Decimal("25.50")


def test_env_invalid_money_raises(monkeypatch, tmp_path):
    monkeypatch.setenv("OPS_RESERVE_USD", "doscientos")
    monkeypatch.setenv("OPS_LEDGER_PATH", str(tmp_path / "ops.json"))

    with pytest.raises(OpsLedgerError):
        get_ops_ledger()


# ─── Contrato HTTP (Track C dashboard) ───────────────────────────────────────

SUMMARY_KEYS = {
    "ops_reserve_usd",
    "ops_burn_mtd",
    "ops_burn_total",
    "ops_reserve_remaining",
    "monthly_cap",
    "cap_exceeded",
    "projected_annual_burn",
    "reserve_exhausted_projection",
    "month",
    "months_observed",
    "entries_count",
    "currency",
}


@pytest.fixture
def api_client(monkeypatch, tmp_path):
    monkeypatch.setenv("OPS_LEDGER_PATH", str(tmp_path / "ops_ledger.json"))
    monkeypatch.setenv("OPS_RESERVE_USD", "200")
    monkeypatch.setenv("OPS_MONTHLY_CAP_USD", "50")
    monkeypatch.setenv("API_KEY", "test-ops-key")
    return TestClient(app)


def test_get_summary_contract(api_client):
    response = api_client.get("/api/ops/summary")
    assert response.status_code == 200

    body = response.json()
    assert set(body) == SUMMARY_KEYS
    # Dinero como string decimal de 2 posiciones: el dashboard no debe ver floats
    assert body["ops_reserve_usd"] == "200.00"
    assert body["ops_burn_mtd"] == "0.00"
    assert body["ops_reserve_remaining"] == "200.00"
    assert body["monthly_cap"] == "50.00"
    assert body["projected_annual_burn"] == "0.00"
    assert body["cap_exceeded"] is False
    assert body["reserve_exhausted_projection"] is False
    assert body["currency"] == "USD"
    assert body["entries_count"] == 0


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
    assert summary["ops_reserve_remaining"] == "187.50"


def test_post_ledger_rejects_invalid_category(api_client):
    response = api_client.post(
        "/api/ops/ledger",
        headers={"Authorization": "Bearer test-ops-key"},
        json={"date": "2026-08-04", "category": "marketing", "amount_usd": "12.50"},
    )
    assert response.status_code == 400


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
