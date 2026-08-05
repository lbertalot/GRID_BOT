"""Unit tests for the unified capital ledger — minimal books (P0 slice S6, ADR-004).

Cubre AC-S6.1..AC-S6.5 de `Docs/product/acceptance-criteria-sprint-kickoff.md`:
allocations 70/20/10 declaradas, suma 100% validada, caps derivados del capital
tradable (no del aportado), consolidado único para el kill, y alcance L0
(PnL de satellites manual, satellites sin live).

Sin red, sin DB.
"""

import json
import os
import sys
from decimal import Decimal

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from app.core.capital_books import (
    KNOWN_BOOK_IDS,
    CapitalBooksConfigError,
    get_books_snapshot,
    get_consolidated_equity,
    load_capital_books_config,
    parse_capital_books_config,
    serialize_books_snapshot,
)

SECRET_MARKERS = ("api_key", "apikey", "secret", "password", "token", "private")


def _raw_config(
    *,
    contributed="1000",
    ops_reserve="200",
    allocations=(("core_grid", "70"), ("sat_systematic", "20"), ("sat_signals", "10")),
    live_enabled=("core_grid",),
    manual_pnl=None,
):
    """Config cruda equivalente al JSON versionado, para ejercitar validaciones."""
    engines = {
        "core_grid": "grid_bot",
        "sat_systematic": "freqtrade",
        "sat_signals": "trading_agents",
    }
    manual_pnl = manual_pnl or {}
    return {
        "version": 1,
        "contributed_capital_usd": contributed,
        "ops_reserve_usd": ops_reserve,
        "books": [
            {
                "book_id": book_id,
                "engine": engines.get(book_id, "unknown"),
                "allocation_pct": pct,
                "live_enabled": book_id in live_enabled,
                "pnl_source": "internal" if book_id == "core_grid" else "manual",
                "manual_pnl": manual_pnl.get(book_id, {}),
            }
            for book_id, pct in allocations
        ],
    }


def _books_by_id(snapshot):
    return {book["book_id"]: book for book in snapshot["books"]}


# ── AC-S6.1 — Books declarados ────────────────────────────────────────────────


def test_versioned_config_declares_70_20_10():
    config = load_capital_books_config()
    allocations = {book.book_id: book.allocation_pct for book in config.books}
    assert allocations == {
        "core_grid": Decimal("70"),
        "sat_systematic": Decimal("20"),
        "sat_signals": Decimal("10"),
    }


def test_snapshot_exposes_required_book_fields():
    snapshot = get_books_snapshot()
    assert [book["book_id"] for book in snapshot["books"]] == list(KNOWN_BOOK_IDS)
    for book in snapshot["books"]:
        for field in (
            "allocation_pct",
            "notional_cap_usd",
            "realized_pnl",
            "unrealized_pnl",
            "live_enabled",
            "pnl_source",
        ):
            assert field in book, f"falta {field} en {book['book_id']}"


# ── AC-S6.2 — Suma 100% validada ──────────────────────────────────────────────


@pytest.mark.parametrize(
    "allocations",
    [
        (("core_grid", "70"), ("sat_systematic", "20"), ("sat_signals", "5")),
        (("core_grid", "70"), ("sat_systematic", "20"), ("sat_signals", "20")),
        (("core_grid", "70.01"), ("sat_systematic", "20"), ("sat_signals", "10")),
    ],
)
def test_allocations_not_summing_100_are_rejected(allocations):
    with pytest.raises(CapitalBooksConfigError) as exc:
        parse_capital_books_config(_raw_config(allocations=allocations))
    assert "100" in str(exc.value)


def test_negative_allocation_is_rejected():
    allocations = (
        ("core_grid", "110"),
        ("sat_systematic", "-10"),
        ("sat_signals", "0"),
    )
    with pytest.raises(CapitalBooksConfigError) as exc:
        parse_capital_books_config(_raw_config(allocations=allocations))
    assert "allocation_pct" in str(exc.value)


# ── AC-S6.3 — Caps derivados del capital tradable, no del aportado ────────────


def test_caps_derived_from_tradable_not_contributed():
    config = parse_capital_books_config(
        _raw_config(contributed="1000", ops_reserve="200")
    )
    assert config.tradable_capital_usd == Decimal("800.00")
    caps = {book["book_id"]: book["notional_cap_usd"] for book in _books_by_id(
        get_books_snapshot(config=config)
    ).values()}
    assert caps["core_grid"] == Decimal("560.00")  # 70% de 800, no de 1000
    assert caps["sat_systematic"] == Decimal("160.00")
    assert caps["sat_signals"] == Decimal("80.00")


@pytest.mark.parametrize(
    "ops_reserve,tradable,expected",
    [
        ("250", "750.00", ("525.00", "150.00", "75.00")),
        ("150", "850.00", ("595.00", "170.00", "85.00")),
    ],
)
def test_caps_for_tradable_capital_band(ops_reserve, tradable, expected):
    config = parse_capital_books_config(
        _raw_config(contributed="1000", ops_reserve=ops_reserve)
    )
    assert config.tradable_capital_usd == Decimal(tradable)
    books = _books_by_id(get_books_snapshot(config=config))
    core, systematic, signals = (Decimal(value) for value in expected)
    assert books["core_grid"]["notional_cap_usd"] == core
    assert books["sat_systematic"]["notional_cap_usd"] == systematic
    assert books["sat_signals"]["notional_cap_usd"] == signals


def test_caps_never_exceed_tradable_capital():
    config = parse_capital_books_config(
        _raw_config(contributed="1000", ops_reserve="175")
    )
    snapshot = get_books_snapshot(config=config)
    allocated = sum(
        (book["notional_cap_usd"] for book in snapshot["books"]), Decimal("0")
    )
    assert allocated <= snapshot["totals"]["tradable_capital"]
    assert snapshot["totals"]["allocated_notional_cap"] == allocated


def test_env_override_of_tradable_capital(monkeypatch):
    monkeypatch.setenv("TRADABLE_CAPITAL_USD", "750")
    config = load_capital_books_config()
    assert config.tradable_capital_usd == Decimal("750.00")
    books = _books_by_id(get_books_snapshot(config=config))
    assert books["core_grid"]["notional_cap_usd"] == Decimal("525.00")


def test_env_override_cannot_eat_the_ops_reserve(monkeypatch):
    # aportado 1000 − reserva ops 200 ⇒ máximo tradable 800 (AC-S5.1)
    monkeypatch.setenv("TRADABLE_CAPITAL_USD", "950")
    with pytest.raises(CapitalBooksConfigError) as exc:
        load_capital_books_config()
    assert "ops_reserve" in str(exc.value)


@pytest.mark.parametrize("value", ["0", "-100", "not-a-number", ""])
def test_invalid_env_override_is_rejected(monkeypatch, value):
    monkeypatch.setenv("TRADABLE_CAPITAL_USD", value)
    with pytest.raises(CapitalBooksConfigError) as exc:
        load_capital_books_config()
    assert "TRADABLE_CAPITAL_USD" in str(exc.value)


# ── AC-S6.4 — Un solo kill consolidado ────────────────────────────────────────


def test_consolidated_totals_sum_books_with_decimal_precision():
    config = parse_capital_books_config(
        _raw_config(
            manual_pnl={
                "sat_systematic": {"realized_pnl": "0.10", "unrealized_pnl": "0.20"},
                "sat_signals": {"realized_pnl": "-0.30", "unrealized_pnl": "0.00"},
            }
        )
    )
    snapshot = get_books_snapshot(
        config=config,
        pnl_overrides={"core_grid": {"realized_pnl": "0.10", "unrealized_pnl": "0"}},
    )
    totals = snapshot["totals"]
    # 0.10 + 0.10 + 0.20 − 0.30 == 0.10 exacto (con float daría 0.10000000000000003)
    assert totals["consolidated_pnl"] == Decimal("0.10")
    assert totals["realized_pnl"] == Decimal("-0.10")
    assert totals["unrealized_pnl"] == Decimal("0.20")
    assert totals["consolidated_equity"] == Decimal("800.10")


def test_consolidated_kill_uses_winner_and_loser_books_together():
    config = parse_capital_books_config(
        _raw_config(
            manual_pnl={"sat_systematic": {"realized_pnl": "40", "unrealized_pnl": "0"}}
        )
    )
    equity = get_consolidated_equity(
        config=config,
        pnl_overrides={"core_grid": {"realized_pnl": "-90", "unrealized_pnl": "0"}},
    )
    # El book ganador no salva al perdedor ni viceversa: el kill mira el neto.
    assert equity == Decimal("750.00")
    assert isinstance(equity, Decimal)


def test_float_amounts_are_rejected_in_money_paths():
    with pytest.raises(CapitalBooksConfigError) as exc:
        get_books_snapshot(pnl_overrides={"core_grid": {"realized_pnl": 12.34}})
    assert "float" in str(exc.value).lower()


# ── AC-S6.5 — L0: satellites en paper, PnL manual ─────────────────────────────


@pytest.mark.parametrize("book_id", ["sat_systematic", "sat_signals"])
def test_satellite_with_live_enabled_is_rejected(book_id):
    with pytest.raises(CapitalBooksConfigError) as exc:
        parse_capital_books_config(
            _raw_config(live_enabled=("core_grid", book_id))
        )
    message = str(exc.value)
    assert book_id in message
    assert "live" in message.lower()


def test_core_grid_is_the_only_live_book_in_l0():
    snapshot = get_books_snapshot()
    books = _books_by_id(snapshot)
    assert books["core_grid"]["live_enabled"] is True
    assert books["sat_systematic"]["live_enabled"] is False
    assert books["sat_signals"]["live_enabled"] is False
    assert snapshot["live_books"] == ["core_grid"]
    assert snapshot["paper_books"] == ["sat_systematic", "sat_signals"]


def test_satellites_have_zero_live_notional_cap():
    snapshot = get_books_snapshot()
    books = _books_by_id(snapshot)
    assert books["core_grid"]["live_notional_cap_usd"] == books["core_grid"][
        "notional_cap_usd"
    ]
    assert books["sat_systematic"]["live_notional_cap_usd"] == Decimal("0.00")
    assert books["sat_signals"]["live_notional_cap_usd"] == Decimal("0.00")
    assert snapshot["totals"]["live_notional_cap"] == books["core_grid"][
        "notional_cap_usd"
    ]


def test_satellite_pnl_is_declared_manual_in_l0():
    snapshot = get_books_snapshot()
    books = _books_by_id(snapshot)
    assert books["core_grid"]["pnl_source"] == "internal"
    assert books["sat_systematic"]["pnl_source"] == "manual"
    assert books["sat_signals"]["pnl_source"] == "manual"
    assert "manual" in snapshot["pnl_note"].lower()


def test_manual_pnl_from_versioned_config_is_used():
    config = parse_capital_books_config(
        _raw_config(
            manual_pnl={
                "sat_signals": {"realized_pnl": "-5.50", "unrealized_pnl": "1.25"}
            }
        )
    )
    book = _books_by_id(get_books_snapshot(config=config))["sat_signals"]
    assert book["realized_pnl"] == Decimal("-5.50")
    assert book["unrealized_pnl"] == Decimal("1.25")
    assert book["total_pnl"] == Decimal("-4.25")


# ── Integridad de la config ───────────────────────────────────────────────────


def test_unknown_book_id_is_rejected():
    allocations = (
        ("core_grid", "70"),
        ("sat_systematic", "20"),
        ("sat_leverage", "10"),
    )
    with pytest.raises(CapitalBooksConfigError) as exc:
        parse_capital_books_config(_raw_config(allocations=allocations))
    assert "sat_leverage" in str(exc.value)


def test_duplicated_book_id_is_rejected():
    allocations = (
        ("core_grid", "70"),
        ("core_grid", "20"),
        ("sat_signals", "10"),
    )
    with pytest.raises(CapitalBooksConfigError) as exc:
        parse_capital_books_config(_raw_config(allocations=allocations))
    assert "duplicado" in str(exc.value).lower()


def test_missing_book_is_rejected():
    allocations = (("core_grid", "80"), ("sat_systematic", "20"))
    with pytest.raises(CapitalBooksConfigError) as exc:
        parse_capital_books_config(_raw_config(allocations=allocations))
    assert "sat_signals" in str(exc.value)


def test_pnl_override_for_unknown_book_is_rejected():
    with pytest.raises(CapitalBooksConfigError) as exc:
        get_books_snapshot(pnl_overrides={"sat_futures": {"realized_pnl": "10"}})
    assert "sat_futures" in str(exc.value)


def test_missing_config_file_fails_with_explicit_reason(tmp_path):
    missing = tmp_path / "no-such-capital-books.json"
    with pytest.raises(CapitalBooksConfigError) as exc:
        load_capital_books_config(path=missing)
    assert str(missing) in str(exc.value)


# ── Serialización / superficie expuesta ───────────────────────────────────────


def test_snapshot_money_values_are_decimal_not_float():
    snapshot = get_books_snapshot()
    money_fields = (
        "notional_cap_usd",
        "live_notional_cap_usd",
        "realized_pnl",
        "unrealized_pnl",
        "total_pnl",
    )
    for book in snapshot["books"]:
        for field in money_fields:
            assert isinstance(book[field], Decimal), f"{book['book_id']}.{field}"
    for value in snapshot["totals"].values():
        assert isinstance(value, Decimal)


def test_serialized_snapshot_uses_strings_for_money():
    payload = serialize_books_snapshot(get_books_snapshot())
    assert payload["totals"]["tradable_capital"] == "800.00"
    core = payload["books"][0]
    assert core["book_id"] == "core_grid"
    assert core["notional_cap_usd"] == "560.00"
    assert core["allocation_pct"] == "70.00"
    # Debe ser JSON-serializable sin conversión a float
    assert json.loads(json.dumps(payload))["totals"]["consolidated_equity"] == "800.00"


def test_snapshot_has_no_secrets():
    dumped = json.dumps(serialize_books_snapshot(get_books_snapshot())).lower()
    for marker in SECRET_MARKERS:
        assert marker not in dumped


# ── Contrato del endpoint (consumido por el dashboard, Track C) ───────────────


@pytest.fixture(scope="module")
def api_client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


def test_books_endpoint_contract(api_client):
    response = api_client.get("/api/capital/books")
    assert response.status_code == 200
    payload = response.json()

    for key in ("config_version", "generated_at", "books", "totals", "live_books",
                "paper_books", "pnl_note"):
        assert key in payload, f"falta la key {key} en el contrato"

    assert [book["book_id"] for book in payload["books"]] == list(KNOWN_BOOK_IDS)
    for book in payload["books"]:
        for key in (
            "book_id",
            "engine",
            "allocation_pct",
            "notional_cap_usd",
            "live_enabled",
            "live_notional_cap_usd",
            "pnl_source",
            "realized_pnl",
            "unrealized_pnl",
            "total_pnl",
        ):
            assert key in book, f"falta {key} en el book {book['book_id']}"

    for key in (
        "contributed_capital",
        "ops_reserve",
        "tradable_capital",
        "allocated_notional_cap",
        "live_notional_cap",
        "realized_pnl",
        "unrealized_pnl",
        "consolidated_pnl",
        "consolidated_equity",
    ):
        assert key in payload["totals"], f"falta {key} en totals"


def test_books_endpoint_is_read_only(api_client):
    assert api_client.post("/api/capital/books", json={}).status_code in (404, 405)
    # POST /api/capital/allocations queda fuera de este slice (follow-up P1)
    assert api_client.post(
        "/api/capital/allocations", json={}
    ).status_code in (404, 405)


def test_books_endpoint_has_no_secrets(api_client):
    dumped = api_client.get("/api/capital/books").text.lower()
    for marker in SECRET_MARKERS:
        assert marker not in dumped
