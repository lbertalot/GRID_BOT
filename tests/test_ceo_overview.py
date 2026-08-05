"""Contract tests for the CEO overview dashboard (slice S3, ADR-005 / RFC-004).

The overview aggregates data owned by other slices (capital risk, ops ledger,
live gate, books, breakers). Those modules may not exist yet, so the endpoint
must degrade honestly: `unavailable` with a null value, never a fabricated zero.

Paper-only: nothing here arms live trading.
"""

from __future__ import annotations

import json
import os
import sys
import types
from datetime import datetime, timedelta, timezone
from decimal import Decimal

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from fastapi.testclient import TestClient

from app.core import ceo_overview
from app.main import app

OVERVIEW_URL = "/api/ceo/overview"
DASHBOARD_URL = "/api/ceo/dashboard"

TEST_API_KEY = "test-ceo-key"
AUTH = {"Authorization": f"Bearer {TEST_API_KEY}"}

# Every key the CEO dashboard promises (AC-S3.1). Removing any of these breaks
# the contract with the view and with S4 (live gate).
REQUIRED_KEYS = {
    "generated_at",
    "effective_mode",
    "mode",
    "gate_ready",
    "blocking_reasons",
    "equity_reconciled",
    "contributed_capital",
    "kill_floor",
    "dd_vs_contributed_pct",
    "pnl_mtd",
    "daily_pnl_pct",
    "breakers",
    "emergency_stop",
    "ops_burn_mtd",
    "ops_reserve_remaining",
    "ops_reserve_total",
    "ops_reserve_committed",
    "ops_policy",
    "books",
    "gate",
    "live_gate_signed",
}

# Widgets served by slices that are not merged into this branch yet.
UPSTREAM_WIDGETS = [
    "equity_reconciled",
    "contributed_capital",
    "kill_floor",
    "dd_vs_contributed_pct",
    "pnl_mtd",
    "daily_pnl_pct",
    "ops_burn_mtd",
    "ops_reserve_remaining",
    "ops_reserve_total",
    "ops_reserve_committed",
    "ops_policy",
    "books",
    "gate",
]


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def paper_env(monkeypatch):
    monkeypatch.setenv("PAPER_TRADING", "true")
    monkeypatch.setenv("FORCE_REAL_MODE", "false")
    monkeypatch.setenv("TRADING_ENABLED", "true")
    monkeypatch.setenv("EMERGENCY_STOP", "false")
    monkeypatch.setenv("API_KEY", TEST_API_KEY)
    monkeypatch.delenv("CEO_DASHBOARD_PUBLIC", raising=False)
    monkeypatch.delenv("CEO_OVERVIEW_STALE_SECONDS", raising=False)
    yield


@pytest.fixture
def fake_modules(monkeypatch):
    """Control which optional upstream modules the aggregator can see.

    Keeps the suite deterministic whether or not tracks A/B/D/E/F are merged.
    """
    registry: dict[str, object | None] = {}

    def _fake_import(module_name: str):
        return registry.get(module_name)

    monkeypatch.setattr(ceo_overview, "_import_optional", _fake_import)
    return registry


@pytest.fixture
def client(paper_env, fake_modules):
    return TestClient(app)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(moment: datetime) -> str:
    return moment.isoformat()


def _module(name: str, **attrs) -> types.ModuleType:
    mod = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(mod, key, value)
    return mod


def _ops_payload(as_of: str, **overrides) -> dict:
    """Shape de `/api/ops/summary` post PR #36 (Track B)."""
    payload = {
        "ops_reserve_total": Decimal("100.00"),
        "ops_reserve_committed": Decimal("15.00"),
        "ops_reserve_remaining": Decimal("85.00"),
        "ops_burn_mtd": Decimal("42.00"),
        "ops_accrued_to_date": Decimal("15.00"),
        "ops_accrual_months": 1,
        "committed_driven_by_burn": False,
        "excluded_categories": ["llm"],
        "l0_policy_violation": False,
        "as_of": as_of,
    }
    payload.update(overrides)
    return payload


def _healthy_registry(registry: dict, *, signers: list[str] | None = None) -> None:
    """Populate every optional module with a healthy, fresh payload."""
    as_of = _iso(_now())
    registry["app.core.capital_risk"] = _module(
        "app.core.capital_risk",
        get_capital_status=lambda: {
            "contributed_capital": Decimal("1000.00"),
            "equity_reconciled": Decimal("1020.50"),
            "kill_floor": Decimal("750.00"),
            "dd_vs_contributed": Decimal("0.0205"),
            "daily_pnl_pct": Decimal("0.004"),
            "risk_state": "normal",
            "as_of": as_of,
        },
    )
    registry["app.core.ops_ledger"] = _module(
        "app.core.ops_ledger",
        get_ops_summary=lambda: _ops_payload(as_of),
    )
    registry["app.core.live_gate"] = _module(
        "app.core.live_gate",
        get_live_gate_status=lambda: {
            "signed": signers is not None and set(signers) >= {"ceo", "desk_lead"},
            "signers": signers if signers is not None else [],
            "config_hash": "abc123",
            "as_of": as_of,
        },
    )
    registry["app.core.capital_books"] = _module(
        "app.core.capital_books",
        get_books=lambda: {
            "books": [
                {"name": "core_grid", "allocation_pct": "70"},
                {"name": "sat_systematic", "allocation_pct": "20"},
                {"name": "sat_signals", "allocation_pct": "10"},
            ],
            "as_of": as_of,
        },
    )
    registry["app.core.breakers_status"] = _module(
        "app.core.breakers_status",
        get_breakers_status=lambda: {
            "open_breakers": [],
            "total_active": 0,
            "emergency_stop": False,
            "as_of": as_of,
        },
    )
    registry["app.core.pnl_ledger"] = _module(
        "app.core.pnl_ledger",
        get_pnl_summary=lambda: {
            "pnl_mtd": Decimal("18.30"),
            "daily_pnl_pct": Decimal("0.004"),
            "as_of": as_of,
        },
    )


def _widget(payload: dict, key: str) -> dict:
    widget = payload[key]
    assert isinstance(widget, dict), f"{key} debe ser un widget, no un valor pelado"
    assert {"status", "value", "as_of", "source", "reason"} <= set(widget), (
        f"{key} no cumple el shape de widget: {widget}"
    )
    assert widget["status"] in {"ok", "unavailable", "stale"}
    return widget


# ─────────────────────────────────────────────────────────────────────────────
# AC-S3.1 — contrato de keys
# ─────────────────────────────────────────────────────────────────────────────


def test_overview_contract_keys_present_even_without_upstream_modules(client):
    response = client.get(OVERVIEW_URL, headers=AUTH)

    assert response.status_code == 200
    payload = response.json()
    missing = REQUIRED_KEYS - set(payload)
    assert not missing, f"faltan keys obligatorias del contrato: {sorted(missing)}"


def test_every_widget_exposes_status_and_timestamp(client, fake_modules):
    _healthy_registry(fake_modules, signers=["ceo", "desk_lead"])

    payload = client.get(OVERVIEW_URL, headers=AUTH).json()

    for key in UPSTREAM_WIDGETS + ["breakers", "emergency_stop"]:
        widget = _widget(payload, key)
        assert widget["status"] == "ok", f"{key} debería estar ok: {widget}"
        assert widget["as_of"], f"{key} debe traer timestamp del dato"


# ─────────────────────────────────────────────────────────────────────────────
# AC-S3.4 — degradación honesta
# ─────────────────────────────────────────────────────────────────────────────


def test_missing_upstream_modules_degrade_to_unavailable_without_inventing_values(
    client,
):
    payload = client.get(OVERVIEW_URL, headers=AUTH).json()

    for key in UPSTREAM_WIDGETS:
        widget = _widget(payload, key)
        assert widget["status"] == "unavailable", f"{key} no debería estar {widget}"
        assert widget["value"] is None, (
            f"{key} inventó un valor con la fuente caída: {widget['value']}"
        )
        assert widget["reason"], f"{key} debe explicar por qué no hay dato"


def test_adapter_exception_does_not_break_the_endpoint(client, fake_modules):
    def _boom():
        raise RuntimeError("ledger caído con Bearer super-secret-token adentro")

    fake_modules["app.core.ops_ledger"] = _module(
        "app.core.ops_ledger", get_ops_summary=_boom
    )

    response = client.get(OVERVIEW_URL, headers=AUTH)

    assert response.status_code == 200
    widget = _widget(response.json(), "ops_burn_mtd")
    assert widget["status"] == "unavailable"
    assert widget["value"] is None
    # El motivo no debe filtrar el mensaje de la excepción (puede traer datos).
    assert "secret" not in widget["reason"].lower()


def test_stale_data_is_flagged_and_keeps_its_timestamp(client, fake_modules):
    old = _iso(_now() - timedelta(hours=3))
    fake_modules["app.core.ops_ledger"] = _module(
        "app.core.ops_ledger",
        get_ops_summary=lambda: {
            "ops_burn_mtd": Decimal("42.00"),
            "ops_reserve_remaining": Decimal("158.00"),
            "as_of": old,
        },
    )

    payload = client.get(OVERVIEW_URL, headers=AUTH).json()

    widget = _widget(payload, "ops_burn_mtd")
    assert widget["status"] == "stale"
    assert widget["as_of"] == old
    assert widget["value"] == "42.00"


# ─────────────────────────────────────────────────────────────────────────────
# AC-S3.3 — modo inequívoco
# ─────────────────────────────────────────────────────────────────────────────


def test_effective_mode_is_paper_by_default(client):
    payload = client.get(OVERVIEW_URL, headers=AUTH).json()

    assert payload["effective_mode"] == "paper"
    assert payload["mode"]["paper_trading"] is True


def test_effective_mode_reflects_real_blocked(client, monkeypatch):
    monkeypatch.setenv("PAPER_TRADING", "false")
    monkeypatch.setenv("FORCE_REAL_MODE", "false")

    payload = client.get(OVERVIEW_URL, headers=AUTH).json()

    assert payload["effective_mode"] == "real_blocked"


# ─────────────────────────────────────────────────────────────────────────────
# Integridad financiera — Decimal serializado como string
# ─────────────────────────────────────────────────────────────────────────────


def test_money_is_serialized_as_decimal_string(client, fake_modules):
    _healthy_registry(fake_modules, signers=["ceo", "desk_lead"])

    payload = client.get(OVERVIEW_URL, headers=AUTH).json()

    for key, expected in [
        ("equity_reconciled", "1020.50"),
        ("contributed_capital", "1000.00"),
        ("kill_floor", "750.00"),
        ("ops_burn_mtd", "42.00"),
        ("ops_reserve_remaining", "85.00"),
        ("ops_reserve_total", "100.00"),
        ("ops_reserve_committed", "15.00"),
        ("pnl_mtd", "18.30"),
    ]:
        value = payload[key]["value"]
        assert isinstance(value, str), f"{key} debe viajar como string, no {type(value)}"
        assert value == expected


# ─────────────────────────────────────────────────────────────────────────────
# AC-S3.2 — sin secrets
# ─────────────────────────────────────────────────────────────────────────────


def test_payload_carries_no_secrets(client, fake_modules, monkeypatch):
    monkeypatch.setenv("BINANCE_API_SECRET", "SUPER-SECRET-VALUE")
    _healthy_registry(fake_modules, signers=["ceo", "desk_lead"])

    raw = json.dumps(client.get(OVERVIEW_URL, headers=AUTH).json()).lower()

    for needle in ("api_key", "apikey", "secret", "token", "password", "private_key"):
        assert needle not in raw, f"el payload expone '{needle}'"
    assert "super-secret-value" not in raw
    assert TEST_API_KEY.lower() not in raw


def test_upstream_payloads_are_scrubbed_before_being_exposed(client, fake_modules):
    fake_modules["app.core.capital_books"] = _module(
        "app.core.capital_books",
        get_books=lambda: {
            "books": [{"name": "core_grid", "api_key": "leaked-key"}],
            "exchange_secret": "leaked-secret",
            "as_of": _iso(_now()),
        },
    )

    raw = json.dumps(client.get(OVERVIEW_URL, headers=AUTH).json())

    assert "leaked-key" not in raw
    assert "leaked-secret" not in raw


# ─────────────────────────────────────────────────────────────────────────────
# AC-S3.5 — semáforo go/no-go (y rule 40)
# ─────────────────────────────────────────────────────────────────────────────


def test_gate_ready_is_false_when_upstream_is_missing(client):
    payload = client.get(OVERVIEW_URL, headers=AUTH).json()

    assert payload["gate_ready"] is False
    assert payload["blocking_reasons"], "un dashboard rojo debe explicar por qué"


def test_gate_ready_is_false_with_a_single_signature(client, fake_modules):
    _healthy_registry(fake_modules, signers=["ceo"])

    payload = client.get(OVERVIEW_URL, headers=AUTH).json()

    assert payload["gate_ready"] is False
    assert any("gate" in reason for reason in payload["blocking_reasons"])


def test_gate_ready_is_false_when_a_breaker_is_open(client, fake_modules):
    _healthy_registry(fake_modules, signers=["ceo", "desk_lead"])
    fake_modules["app.core.breakers_status"] = _module(
        "app.core.breakers_status",
        get_breakers_status=lambda: {
            "open_breakers": ["balance_discrepancy"],
            "total_active": 1,
            "emergency_stop": False,
            "as_of": _iso(_now()),
        },
    )

    payload = client.get(OVERVIEW_URL, headers=AUTH).json()

    assert payload["gate_ready"] is False
    assert any("breaker" in reason for reason in payload["blocking_reasons"])


def test_gate_ready_is_true_only_with_dual_signature_and_green_widgets(
    client, fake_modules
):
    _healthy_registry(fake_modules, signers=["ceo", "desk_lead"])

    payload = client.get(OVERVIEW_URL, headers=AUTH).json()

    assert payload["gate_ready"] is True
    assert payload["blocking_reasons"] == []


def test_gate_ready_never_implies_live_is_armed(client, fake_modules):
    """gate_ready es lectura, no una autorización (rule 40)."""
    _healthy_registry(fake_modules, signers=["ceo", "desk_lead"])

    payload = client.get(OVERVIEW_URL, headers=AUTH).json()

    assert payload["effective_mode"] == "paper"
    assert payload["mode"]["force_real_mode"] is False


# ─────────────────────────────────────────────────────────────────────────────
# AC-S3.6 — read-only
# ─────────────────────────────────────────────────────────────────────────────


def test_ceo_router_exposes_only_read_methods():
    from app.api import ceo_routes

    for route in ceo_routes.router.routes:
        assert set(route.methods) <= {"GET", "HEAD"}, (
            f"{route.path} expone escritura desde el dashboard"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Vista HTML
# ─────────────────────────────────────────────────────────────────────────────


def test_dashboard_page_renders_mode_first(client):
    response = client.get(DASHBOARD_URL, headers=AUTH)

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    body = response.text
    assert "PAPER" in body
    # El modo tiene que estar antes que cualquier cifra de riesgo.
    assert body.index("PAPER") < body.index("Kill floor")


def test_dashboard_page_marks_unavailable_widgets(client):
    body = client.get(DASHBOARD_URL, headers=AUTH).text

    assert "Sin datos" in body
    assert "status-unavailable" in body


def test_dashboard_page_does_not_claim_live_readiness_without_gate(client):
    body = client.get(DASHBOARD_URL, headers=AUTH).text.lower()

    assert "no-go" in body
    assert "listo para live" not in body


def _card_html(body: str, label: str) -> str:
    """Fragmento HTML de la tarjeta que lleva ese rótulo."""
    position = body.index(label)
    return body[body.rindex("<article", 0, position) : body.index("</article>", position)]


def test_dashboard_paints_risk_and_not_only_data_freshness(client, fake_modules):
    """Un dato fresco puede ser una mala noticia: el color mira el riesgo."""
    _healthy_registry(fake_modules, signers=["ceo"])
    fake_modules["app.core.capital_risk"] = _module(
        "app.core.capital_risk",
        get_capital_status=lambda: {
            "contributed_capital": Decimal("1000.00"),
            "equity_reconciled": Decimal("820.00"),
            "kill_floor": Decimal("750.00"),
            "dd_vs_contributed": Decimal("-0.18"),
            "risk_state": "alert",
            "as_of": _iso(_now()),
        },
    )

    body = client.get(DASHBOARD_URL, headers=AUTH).text

    assert "risk-warn" in _card_html(body, "DD vs aportado")
    assert "risk-ok" not in _card_html(body, "DD vs aportado")


def test_dashboard_never_paints_an_unsigned_gate_as_green(client, fake_modules):
    _healthy_registry(fake_modules, signers=["ceo"])

    gate_card = _card_html(client.get(DASHBOARD_URL, headers=AUTH).text, "Live gate")

    assert "risk-ok" not in gate_card


def test_dashboard_paints_kill_floor_breach_as_danger(client, fake_modules):
    _healthy_registry(fake_modules, signers=["ceo", "desk_lead"])
    fake_modules["app.core.capital_risk"] = _module(
        "app.core.capital_risk",
        get_capital_status=lambda: {
            "contributed_capital": Decimal("1000.00"),
            "equity_reconciled": Decimal("740.00"),
            "kill_floor": Decimal("750.00"),
            "dd_vs_contributed": Decimal("-0.26"),
            "risk_state": "kill",
            "as_of": _iso(_now()),
        },
    )

    body = client.get(DASHBOARD_URL, headers=AUTH).text

    assert "risk-danger" in _card_html(body, "Equity reconciliado")
    assert "risk-danger" in _card_html(body, "DD vs aportado")


# ─────────────────────────────────────────────────────────────────────────────
# Superficie de exposición
# ─────────────────────────────────────────────────────────────────────────────


def test_overview_requires_auth_by_default(client):
    assert client.get(OVERVIEW_URL).status_code == 401


def test_overview_can_be_opened_read_only_when_explicitly_public(client, monkeypatch):
    monkeypatch.setenv("CEO_DASHBOARD_PUBLIC", "true")

    response = client.get(OVERVIEW_URL)

    assert response.status_code == 200
    assert response.json()["effective_mode"] == "paper"


# ─────────────────────────────────────────────────────────────────────────────
# Track D (PR #35): el gate es material autenticado. El overview no puede
# convertirse en el oráculo sin auth que Security acaba de cerrar.
# ─────────────────────────────────────────────────────────────────────────────


def test_authenticated_overview_keeps_the_full_gate_detail(client, fake_modules):
    _healthy_registry(fake_modules, signers=["ceo"])

    gate = client.get(OVERVIEW_URL, headers=AUTH).json()["gate"]["value"]

    assert gate["signers"] == ["ceo"]
    assert gate["config_hash"] == "abc123"


def test_public_overview_redacts_signers_and_config_hash(
    client, fake_modules, monkeypatch
):
    monkeypatch.setenv("CEO_DASHBOARD_PUBLIC", "true")
    _healthy_registry(fake_modules, signers=["ceo"])

    payload = client.get(OVERVIEW_URL).json()

    gate = payload["gate"]["value"]
    assert gate["signed"] is False
    assert gate["detail_requires_auth"] is True
    assert "signers" not in gate
    assert "config_hash" not in gate
    assert "ceo" not in json.dumps(payload).lower().replace("ceo_", "")


def test_public_overview_does_not_enumerate_the_weak_controls(
    client, fake_modules, monkeypatch
):
    monkeypatch.setenv("CEO_DASHBOARD_PUBLIC", "true")
    _healthy_registry(fake_modules, signers=["ceo"])

    payload = client.get(OVERVIEW_URL).json()

    assert payload["gate_ready"] is False
    assert len(payload["blocking_reasons"]) == 1
    assert "autenticaci" in payload["blocking_reasons"][0]


def test_public_overview_still_exposes_the_mode_badge(client, monkeypatch):
    monkeypatch.setenv("CEO_DASHBOARD_PUBLIC", "true")

    payload = client.get(OVERVIEW_URL).json()

    assert payload["effective_mode"] == "paper"
    assert payload["live_gate_signed"] is False


def test_live_gate_badge_is_fail_closed_when_no_source_answers(client):
    payload = client.get(OVERVIEW_URL, headers=AUTH).json()

    assert payload["live_gate_signed"] is False
    assert payload["gate"]["status"] == "unavailable"


def test_live_gate_badge_follows_the_trading_mode_snapshot(client, monkeypatch):
    """Cuando Track D extienda el snapshot, el badge sale de ahí."""
    monkeypatch.setattr(
        "app.core.ceo_overview.get_trading_mode_snapshot",
        lambda: {
            "paper_trading": True,
            "force_real_mode": False,
            "trading_enabled": True,
            "emergency_stop": False,
            "binance_testnet": False,
            "effective_mode": "paper",
            "live_gate_signed": True,
        },
    )

    payload = client.get(OVERVIEW_URL, headers=AUTH).json()

    assert payload["live_gate_signed"] is True


def test_gate_adapter_without_authorization_degrades_instead_of_failing(
    client, fake_modules
):
    from fastapi import HTTPException

    def _unauthorized():
        raise HTTPException(status_code=401, detail="Falta Authorization")

    fake_modules["app.core.live_gate"] = _module(
        "app.core.live_gate", get_live_gate_status=_unauthorized
    )

    response = client.get(OVERVIEW_URL, headers=AUTH)

    assert response.status_code == 200
    widget = _widget(response.json(), "gate")
    assert widget["status"] == "unavailable"
    assert widget["value"] is None
    assert "autorizaci" in widget["reason"]


# ─────────────────────────────────────────────────────────────────────────────
# Track B (PR #36): techo de reserva ≠ plata comprometida. Confundirlos era el
# falso positivo que el CEO eliminó.
# ─────────────────────────────────────────────────────────────────────────────


def test_ops_widget_separates_total_committed_and_remaining(client, fake_modules):
    _healthy_registry(fake_modules, signers=["ceo", "desk_lead"])

    payload = client.get(OVERVIEW_URL, headers=AUTH).json()

    assert payload["ops_reserve_total"]["value"] == "100.00"
    assert payload["ops_reserve_committed"]["value"] == "15.00"
    assert payload["ops_reserve_remaining"]["value"] == "85.00"
    assert payload["ops_burn_mtd"]["value"] == "42.00"


def test_committed_never_falls_back_to_the_reserve_ceiling(client, fake_modules):
    """Sin `ops_reserve_committed` no hay número: el techo no lo reemplaza."""
    fake_modules["app.core.ops_ledger"] = _module(
        "app.core.ops_ledger",
        get_ops_summary=lambda: {
            "ops_reserve_total": Decimal("100.00"),
            "ops_reserve_remaining": Decimal("85.00"),
            "ops_burn_mtd": Decimal("15.00"),
            "as_of": _iso(_now()),
        },
    )

    payload = client.get(OVERVIEW_URL, headers=AUTH).json()

    committed = _widget(payload, "ops_reserve_committed")
    assert committed["status"] == "unavailable"
    assert committed["value"] is None


def test_pre_rename_ops_payload_is_not_consumed_silently(client, fake_modules):
    """`ops_reserve_usd` es el contrato viejo: mejor sin dato que con dato ambiguo."""
    fake_modules["app.core.ops_ledger"] = _module(
        "app.core.ops_ledger",
        get_ops_summary=lambda: {
            "ops_reserve_usd": Decimal("200.00"),
            "ops_burn_mtd": Decimal("42.00"),
            "as_of": _iso(_now()),
        },
    )

    payload = client.get(OVERVIEW_URL, headers=AUTH).json()

    assert _widget(payload, "ops_reserve_total")["value"] is None
    assert _widget(payload, "ops_reserve_committed")["value"] is None
    assert "200.00" not in json.dumps(payload)


def test_l0_policy_violation_blocks_the_gate(client, fake_modules):
    _healthy_registry(fake_modules, signers=["ceo", "desk_lead"])
    fake_modules["app.core.ops_ledger"] = _module(
        "app.core.ops_ledger",
        get_ops_summary=lambda: _ops_payload(_iso(_now()), l0_policy_violation=True),
    )

    payload = client.get(OVERVIEW_URL, headers=AUTH).json()

    assert payload["gate_ready"] is False
    assert any("ops" in reason.lower() for reason in payload["blocking_reasons"])


def test_committed_driven_by_burn_is_flagged_without_blocking(client, fake_modules):
    _healthy_registry(fake_modules, signers=["ceo", "desk_lead"])
    fake_modules["app.core.ops_ledger"] = _module(
        "app.core.ops_ledger",
        get_ops_summary=lambda: _ops_payload(
            _iso(_now()), committed_driven_by_burn=True
        ),
    )

    payload = client.get(OVERVIEW_URL, headers=AUTH).json()

    assert payload["ops_policy"]["value"]["committed_driven_by_burn"] is True
    assert payload["gate_ready"] is True


def test_dashboard_ops_card_shows_remaining_over_the_ceiling(client, fake_modules):
    _healthy_registry(fake_modules, signers=["ceo", "desk_lead"])

    body = client.get(DASHBOARD_URL, headers=AUTH).text

    assert "USD 85.00 / 100.00" in _card_html(body, "Reserva ops")
    committed_card = _card_html(body, "Ops committed")
    assert "USD 15.00" in committed_card
    assert "tradable" in committed_card


def test_dashboard_paints_the_policy_violation_as_danger(client, fake_modules):
    _healthy_registry(fake_modules, signers=["ceo", "desk_lead"])
    fake_modules["app.core.ops_ledger"] = _module(
        "app.core.ops_ledger",
        get_ops_summary=lambda: _ops_payload(_iso(_now()), l0_policy_violation=True),
    )

    body = client.get(DASHBOARD_URL, headers=AUTH).text

    assert "risk-danger" in _card_html(body, "Política ops L0")


def test_public_dashboard_shows_the_badge_but_not_the_signers(client, monkeypatch):
    monkeypatch.setenv("CEO_DASHBOARD_PUBLIC", "true")

    body = client.get(DASHBOARD_URL).text

    assert "PAPER" in body
    assert "Gate: sin firma" in body
    assert "detalle con autenticación" in body.lower()
