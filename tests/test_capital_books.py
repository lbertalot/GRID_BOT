"""Unit tests for the unified capital ledger — minimal books (P0 slice S6, ADR-004).

Cubre AC-S6.1..AC-S6.5 de `Docs/product/acceptance-criteria-sprint-kickoff.md` con la
política de CEO Amendment 01 (2026-08-05): techo de ops ≤ USD 100 devengado
mensualmente, y `tradable_capital = contributed − ops_reserve_committed`.

Sin red, sin DB.
"""

import json
import os
import sys
import types
from decimal import Decimal

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from app.core.capital_books import (
    KNOWN_BOOK_IDS,
    L0_OPS_RESERVE_TOTAL_USD,
    OPS_LEDGER_COMMITTED_METHOD,
    OPS_LEDGER_FACTORY,
    OPS_LEDGER_MODULE,
    OPS_LEDGER_TOTAL_ATTR,
    OPS_LEDGER_TRADABLE_FN,
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
    ops_reserve_total="100",
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
        "version": 2,
        "contributed_capital_usd": contributed,
        "ops_reserve_total_usd": ops_reserve_total,
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


@pytest.fixture(autouse=True)
def _clean_capital_env(monkeypatch):
    """Los tests declaran su propia política; ninguno hereda env del entorno."""
    monkeypatch.delenv("TRADABLE_CAPITAL_USD", raising=False)
    monkeypatch.delenv("OPS_RESERVE_COMMITTED_USD", raising=False)
    monkeypatch.delenv("CAPITAL_BOOKS_CONFIG_PATH", raising=False)


@pytest.fixture
def no_ops_ledger(monkeypatch):
    """Simula que el módulo del Track B todavía no existe.

    Explícito a propósito: cuando #36 mergee, `app.core.ops_ledger` va a existir de
    verdad y estos tests seguirían pasando por accidente (o fallando) según la rama.
    """
    monkeypatch.setitem(sys.modules, OPS_LEDGER_MODULE, None)


@pytest.fixture
def fake_ops_ledger(monkeypatch):
    """Doble del módulo del Track B (PR #36) con su contrato público real.

    `get_ops_ledger()` → objeto con `committed_usd()` y `reserve_total_usd`, más el
    helper puro `compute_tradable_capital(contributed, committed)`.
    """
    calls = {"compute_tradable_capital": []}

    def _install(committed, total="100", raises=False):
        module = types.ModuleType(OPS_LEDGER_MODULE)

        class _Ledger:
            @property
            def reserve_total_usd(self):
                return total

            def committed_usd(self, now=None):
                if raises:
                    raise RuntimeError("ops ledger caído")
                return committed

        def _compute_tradable_capital(contributed_capital, ops_reserve_committed):
            calls["compute_tradable_capital"].append(
                (contributed_capital, ops_reserve_committed)
            )
            return Decimal(str(contributed_capital)) - Decimal(
                str(ops_reserve_committed)
            )

        setattr(module, OPS_LEDGER_FACTORY, _Ledger)
        setattr(module, OPS_LEDGER_TRADABLE_FN, _compute_tradable_capital)
        assert hasattr(_Ledger(), OPS_LEDGER_COMMITTED_METHOD)
        assert hasattr(_Ledger(), OPS_LEDGER_TOTAL_ATTR)
        monkeypatch.setitem(sys.modules, OPS_LEDGER_MODULE, module)
        return calls

    return _install


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


# ── AC-S6.3 — Caps derivados del piso de capital tradable ─────────────────────
# CEO Amendment 01: techo de ops ≤ 100 ⇒ piso tradable 900 ⇒ caps 630/180/90.


def test_caps_derived_from_tradable_floor_not_contributed():
    config = parse_capital_books_config(
        _raw_config(contributed="1000", ops_reserve_total="100")
    )
    assert config.tradable_capital_floor_usd == Decimal("900.00")
    books = _books_by_id(get_books_snapshot(config=config))
    assert books["core_grid"]["notional_cap_usd"] == Decimal("630.00")  # 70% de 900
    assert books["sat_systematic"]["notional_cap_usd"] == Decimal("180.00")
    assert books["sat_signals"]["notional_cap_usd"] == Decimal("90.00")


def test_default_versioned_config_uses_the_amended_ops_ceiling():
    config = load_capital_books_config()
    assert config.ops_reserve_total_usd == Decimal("100.00")
    assert config.tradable_capital_floor_usd == Decimal("900.00")


def test_ops_reserve_total_above_l0_policy_is_rejected():
    # El techo viejo (150–250) ya no es válido: CEO Amendment 01 lo bajó a 100.
    with pytest.raises(CapitalBooksConfigError) as exc:
        parse_capital_books_config(_raw_config(ops_reserve_total="200"))
    message = str(exc.value)
    assert str(L0_OPS_RESERVE_TOTAL_USD) in message
    assert "Amendment" in message


def test_caps_never_exceed_the_tradable_floor():
    # Piso 900.05: fuerza redondeo y verifica que ROUND_DOWN nunca sobre-asigna.
    config = parse_capital_books_config(
        _raw_config(contributed="1000.05", ops_reserve_total="100")
    )
    snapshot = get_books_snapshot(config=config)
    caps = {book["book_id"]: book["notional_cap_usd"] for book in snapshot["books"]}
    assert caps["core_grid"] == Decimal("630.03")  # 630.035 truncado, no 630.04
    assert caps["sat_signals"] == Decimal("90.00")  # 90.005 truncado
    allocated = sum(caps.values(), Decimal("0"))
    assert allocated <= snapshot["totals"]["tradable_capital_floor"]
    assert allocated <= snapshot["totals"]["tradable_capital"]
    assert snapshot["totals"]["allocated_notional_cap"] == allocated


def test_env_override_of_tradable_capital(monkeypatch):
    monkeypatch.setenv("TRADABLE_CAPITAL_USD", "850")
    config = load_capital_books_config()
    assert config.tradable_capital_floor_usd == Decimal("850.00")
    books = _books_by_id(get_books_snapshot(config=config))
    assert books["core_grid"]["notional_cap_usd"] == Decimal("595.00")


def test_env_override_cannot_eat_the_ops_reserve(monkeypatch):
    # aportado 1000 − techo ops 100 ⇒ máximo 900 para dimensionar books
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


# ── Decisión de diseño: caps fijos sobre el piso, tradable real flotante ──────


def test_caps_do_not_move_while_ops_accrues():
    """El devengo mensual de ops no debe mover el sizing del desk.

    Los caps se fijan sobre el piso (contributed − techo de ops); sólo el tradable
    real y el equity consolidado siguen al devengado.
    """
    caps_por_mes = []
    for committed in ("0", "15", "30", "100"):
        snapshot = get_books_snapshot(ops_reserve_committed=committed)
        caps_por_mes.append(
            {book["book_id"]: book["notional_cap_usd"] for book in snapshot["books"]}
        )
    assert all(caps == caps_por_mes[0] for caps in caps_por_mes)
    assert caps_por_mes[0]["core_grid"] == Decimal("630.00")


@pytest.mark.parametrize(
    "committed,tradable",
    [
        ("0", "1000.00"),  # default seguro: nada devengado todavía
        ("15", "985.00"),  # ~1 mes de devengo
        ("30", "970.00"),  # ~2 meses: escenario esperado al go-live 2026-09-15
        ("100", "900.00"),  # techo consumido: tradable toca el piso
    ],
)
def test_tradable_capital_follows_committed_ops(committed, tradable):
    snapshot = get_books_snapshot(ops_reserve_committed=committed)
    totals = snapshot["totals"]
    assert totals["ops_reserve_committed"] == Decimal(committed)
    assert totals["tradable_capital"] == Decimal(tradable)
    assert totals["tradable_capital_floor"] == Decimal("900.00")
    assert totals["consolidated_equity"] == Decimal(tradable)


def test_go_live_scenario_2026_09_15(fake_ops_ledger):
    """Escenario del contrato de Track B: committed 15 ⇒ tradable 985, caps intactos."""
    fake_ops_ledger(Decimal("15.00"), total=Decimal("100.00"))
    snapshot = get_books_snapshot()
    totals = snapshot["totals"]
    assert totals["ops_reserve_total"] == Decimal("100.00")
    assert totals["ops_reserve_committed"] == Decimal("15.00")
    assert totals["tradable_capital"] == Decimal("985.00")
    assert totals["tradable_capital_floor"] == Decimal("900.00")
    assert totals["consolidated_equity"] == Decimal("985.00")
    caps = {book["book_id"]: book["notional_cap_usd"] for book in snapshot["books"]}
    assert caps == {
        "core_grid": Decimal("630.00"),
        "sat_systematic": Decimal("180.00"),
        "sat_signals": Decimal("90.00"),
    }


def test_committed_ops_is_read_from_ops_ledger_when_available(fake_ops_ledger):
    fake_ops_ledger(Decimal("22.50"))
    snapshot = get_books_snapshot()
    assert snapshot["ops_reserve_committed_source"] == "ops_ledger"
    assert snapshot["ops_reserve_total_source"] == "ops_ledger"
    assert snapshot["totals"]["ops_reserve_committed"] == Decimal("22.50")
    assert snapshot["totals"]["tradable_capital"] == Decimal("977.50")


def test_tradable_capital_uses_track_b_helper(fake_ops_ledger):
    """Un solo contrato para el tradable: no derivamos el número por nuestra cuenta."""
    calls = fake_ops_ledger(Decimal("15.00"))
    get_books_snapshot()
    assert calls["compute_tradable_capital"] == [(Decimal("1000.00"), Decimal("15.00"))]


def test_ops_ledger_total_drives_the_caps_over_the_local_config(fake_ops_ledger):
    """Si ops sube su techo, los caps bajan: nunca dimensionamos contra plata de ops."""
    fake_ops_ledger(Decimal("0.00"), total=Decimal("150.00"))
    snapshot = get_books_snapshot()
    assert snapshot["totals"]["ops_reserve_total"] == Decimal("150.00")
    assert snapshot["totals"]["tradable_capital_floor"] == Decimal("850.00")
    caps = {book["book_id"]: book["notional_cap_usd"] for book in snapshot["books"]}
    assert caps["core_grid"] == Decimal("595.00")
    assert caps["sat_systematic"] == Decimal("170.00")
    assert caps["sat_signals"] == Decimal("85.00")


def test_ops_ledger_wins_over_env(monkeypatch, fake_ops_ledger):
    monkeypatch.setenv("OPS_RESERVE_COMMITTED_USD", "10")
    fake_ops_ledger("25")
    snapshot = get_books_snapshot()
    assert snapshot["ops_reserve_committed_source"] == "ops_ledger"
    assert snapshot["totals"]["ops_reserve_committed"] == Decimal("25.00")


def test_env_is_used_when_ops_ledger_is_absent(monkeypatch, no_ops_ledger):
    monkeypatch.setenv("OPS_RESERVE_COMMITTED_USD", "12.50")
    snapshot = get_books_snapshot()
    assert snapshot["ops_reserve_committed_source"] == "env"
    assert snapshot["ops_reserve_total_source"] == "config"
    assert snapshot["totals"]["ops_reserve_committed"] == Decimal("12.50")


def test_default_committed_is_zero_and_flagged_as_default(no_ops_ledger):
    snapshot = get_books_snapshot()
    assert snapshot["ops_reserve_committed_source"] == "default"
    assert snapshot["totals"]["ops_reserve_committed"] == Decimal("0.00")


def test_broken_ops_ledger_degrades_honestly(fake_ops_ledger):
    fake_ops_ledger(None, raises=True)
    snapshot = get_books_snapshot()
    # No mentimos con un número viejo ni tumbamos la lectura de books.
    assert snapshot["ops_reserve_committed_source"] == "unavailable"
    assert snapshot["totals"]["ops_reserve_committed"] == Decimal("0.00")
    # El techo sigue siendo legible desde la config versionada.
    assert snapshot["totals"]["ops_reserve_total"] == Decimal("100.00")
    assert snapshot["totals"]["tradable_capital_floor"] == Decimal("900.00")


def test_ops_ledger_returning_float_is_not_trusted(fake_ops_ledger):
    fake_ops_ledger(22.5)
    snapshot = get_books_snapshot()
    assert snapshot["ops_reserve_committed_source"] == "unavailable"


def test_committed_over_the_cap_is_flagged_not_swallowed():
    snapshot = get_books_snapshot(ops_reserve_committed="120")
    assert snapshot["ops_reserve_over_cap"] is True
    assert snapshot["totals"]["tradable_capital"] == Decimal("880.00")


def test_committed_within_cap_is_not_flagged():
    assert get_books_snapshot(ops_reserve_committed="30")["ops_reserve_over_cap"] is False


@pytest.mark.parametrize("committed", ["-1", "1000", "1200"])
def test_impossible_committed_ops_is_rejected(committed):
    with pytest.raises(CapitalBooksConfigError) as exc:
        get_books_snapshot(ops_reserve_committed=committed)
    assert "ops_reserve_committed" in str(exc.value)


def test_invalid_committed_env_is_rejected(monkeypatch, no_ops_ledger):
    monkeypatch.setenv("OPS_RESERVE_COMMITTED_USD", "veinte")
    with pytest.raises(CapitalBooksConfigError) as exc:
        get_books_snapshot()
    assert "OPS_RESERVE_COMMITTED_USD" in str(exc.value)


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
        ops_reserve_committed="20",
        pnl_overrides={"core_grid": {"realized_pnl": "0.10", "unrealized_pnl": "0"}},
    )
    totals = snapshot["totals"]
    # 0.10 + 0.10 + 0.20 − 0.30 == 0.10 exacto (con float daría 0.10000000000000003)
    assert totals["consolidated_pnl"] == Decimal("0.10")
    assert totals["realized_pnl"] == Decimal("-0.10")
    assert totals["unrealized_pnl"] == Decimal("0.20")
    assert totals["consolidated_equity"] == Decimal("980.10")


def test_consolidated_kill_uses_winner_and_loser_books_together():
    config = parse_capital_books_config(
        _raw_config(
            manual_pnl={"sat_systematic": {"realized_pnl": "40", "unrealized_pnl": "0"}}
        )
    )
    equity = get_consolidated_equity(
        config=config,
        ops_reserve_committed="30",
        pnl_overrides={"core_grid": {"realized_pnl": "-90", "unrealized_pnl": "0"}},
    )
    # El book ganador no salva al perdedor ni viceversa: el kill mira el neto.
    assert equity == Decimal("920.00")  # (1000 − 30) − 90 + 40
    assert isinstance(equity, Decimal)


def test_float_amounts_are_rejected_in_money_paths():
    with pytest.raises(CapitalBooksConfigError) as exc:
        get_books_snapshot(pnl_overrides={"core_grid": {"realized_pnl": 12.34}})
    assert "float" in str(exc.value).lower()


# ── AC-S6.5 — L0: satellites en paper, PnL manual ─────────────────────────────


@pytest.mark.parametrize("book_id", ["sat_systematic", "sat_signals"])
def test_satellite_with_live_enabled_is_rejected(book_id):
    with pytest.raises(CapitalBooksConfigError) as exc:
        parse_capital_books_config(_raw_config(live_enabled=("core_grid", book_id)))
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
    assert books["core_grid"]["live_notional_cap_usd"] == Decimal("630.00")
    assert books["sat_systematic"]["live_notional_cap_usd"] == Decimal("0.00")
    assert books["sat_signals"]["live_notional_cap_usd"] == Decimal("0.00")
    assert snapshot["totals"]["live_notional_cap"] == Decimal("630.00")


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
    payload = serialize_books_snapshot(get_books_snapshot(ops_reserve_committed="15"))
    assert payload["totals"]["tradable_capital"] == "985.00"
    assert payload["totals"]["tradable_capital_floor"] == "900.00"
    assert payload["totals"]["ops_reserve_total"] == "100.00"
    assert payload["totals"]["ops_reserve_committed"] == "15.00"
    core = payload["books"][0]
    assert core["book_id"] == "core_grid"
    assert core["notional_cap_usd"] == "630.00"
    assert core["allocation_pct"] == "70.00"
    # Debe ser JSON-serializable sin conversión a float
    assert json.loads(json.dumps(payload))["totals"]["consolidated_equity"] == "985.00"


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

    for key in (
        "config_version",
        "generated_at",
        "books",
        "totals",
        "live_books",
        "paper_books",
        "pnl_note",
        "notional_cap_policy",
        "ops_reserve_total_source",
        "ops_reserve_committed_source",
        "ops_reserve_over_cap",
        "capital_note",
    ):
        assert key in payload, f"falta la key {key} en el contrato"

    assert payload["notional_cap_policy"] == "fixed_on_tradable_floor"
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
        "ops_reserve_total",
        "ops_reserve_committed",
        "tradable_capital",
        "tradable_capital_floor",
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
    assert api_client.post("/api/capital/allocations", json={}).status_code in (404, 405)


def test_books_endpoint_has_no_secrets(api_client):
    dumped = api_client.get("/api/capital/books").text.lower()
    for marker in SECRET_MARKERS:
        assert marker not in dumped
