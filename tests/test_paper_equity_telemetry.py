"""S10 — Telemetría de equity paper para el tear sheet.

Cubre los gaps bloqueantes de `Docs/engineering/tear-sheet-spec.md` §6.1/§6.2 y las
cuatro adiciones que `Docs/squad/desk-policy-l0.md` v2 §6/§8 reclasificó como
bloqueantes de la ventana:

- I-3 serie de equity paper real          - I-8  `cycle_id` (contar ciclos ≥120)
- I-7 precio de marcación real            - I-12 `config_hash` (gate A1)
- I-5 fee descontada del balance paper     - I-13 cierre diario 00:00 UTC
- I-4 una sola fuente de verdad del ledger - I-6  slippage simulado (2 bps/lado)

Denominador maestro del MaxDD: **capital desplegado** (desk-policy-l0 §3.3).

Reglas: todo el dinero en `Decimal`, cero red, cero exchange.
"""

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.core.paper_equity_ledger import (
    SCHEMA_VERSION,
    InsufficientPaperInventory,
    MarkPriceUnavailable,
    PaperCostModel,
    PaperEquityLedger,
    PaperEquitySeries,
    compute_config_hash,
    compute_paper_portfolio_value,
    daily_close_anchor,
    resolve_grid_config_hash,
)

BTC = "BTCUSDT"
D = Decimal

# Config congelada de desk-policy-l0 §2.4 (spacing 100 bps, 10 niveles, USD 200)
CONFIG_VENTANA = {
    "symbol": "ETHUSDT",
    "deployed_notional_usdt": "200",
    "levels": 10,
    "notional_per_level_usdt": "20",
    "spacing_bps": 100,
    "range_pct": 5,
    "leverage": 1,
}


class FakeMarkPriceFeed:
    """Feed de precios inyectable. Nunca toca la red."""

    def __init__(self, prices):
        self.prices = {k: D(str(v)) for k, v in prices.items()}
        self.calls = 0

    def set_price(self, symbol, price):
        self.prices[symbol] = D(str(price))

    def get_price(self, symbol: str) -> Decimal:
        self.calls += 1
        try:
            return self.prices[symbol]
        except KeyError as exc:
            raise MarkPriceUnavailable(symbol) from exc


@pytest.fixture
def ledger() -> PaperEquityLedger:
    # Wallet de tests de contabilidad (notional 500–1000). El cap L0-A=200
    # vive en tests/test_paper_deployed_notional_cap.py.
    return PaperEquityLedger(initial_cash=D("1000"), deployed_capital=D("1000"))


# ---------------------------------------------------------------------------
# I-3 / I-7 — el equity paper deja de ser constante: se marca a precio real
# ---------------------------------------------------------------------------


def test_equity_mtm_cambia_cuando_cambia_el_precio(ledger):
    ledger.record_buy(BTC, quantity=D("0.01"), price=D("50000"), grid_level=0)

    equity_50k = ledger.mark_to_market({BTC: D("50000")})
    equity_60k = ledger.mark_to_market({BTC: D("60000")})

    assert equity_60k != equity_50k
    # 0,01 BTC × +10.000 USDT = +100 USDT de inventario marcado
    assert equity_60k - equity_50k == D("100")


def test_snapshot_paper_usa_el_feed_y_no_una_constante(ledger):
    ledger.record_buy(BTC, quantity=D("0.01"), price=D("50000"), grid_level=0)
    feed = FakeMarkPriceFeed({BTC: "61234.56"})
    series = PaperEquitySeries()

    primero = compute_paper_portfolio_value(
        ledger=ledger, price_feed=feed, series=series
    )
    feed.set_price(BTC, "48000")
    segundo = compute_paper_portfolio_value(
        ledger=ledger, price_feed=feed, series=series
    )

    assert primero["btc_price"] == pytest.approx(61234.56)
    assert segundo["btc_price"] == pytest.approx(48000.0)
    assert primero["total_value_usdt"] != segundo["total_value_usdt"]
    # El bug histórico: balances fijos (1000 USDT / 0,01 BTC) y BTC=50000.
    assert primero["total_value_usdt"] != 1500.0
    assert len(series.samples) == 2


def test_snapshot_paper_no_inventa_precio_si_el_feed_no_responde(ledger):
    ledger.record_buy(BTC, quantity=D("0.01"), price=D("50000"), grid_level=0)
    feed = FakeMarkPriceFeed({})  # ticker caído

    assert compute_paper_portfolio_value(ledger=ledger, price_feed=feed) is None


# ---------------------------------------------------------------------------
# I-5 / I-6 — comisiones y slippage salen del balance paper (24 bps round-trip)
# ---------------------------------------------------------------------------


def test_round_trip_descuenta_24_bps_exactos(ledger):
    notional = D("500")  # 0,01 BTC @ 50.000

    ledger.record_buy(BTC, quantity=D("0.01"), price=D("50000"), grid_level=0)
    ledger.record_sell(BTC, quantity=D("0.01"), price=D("50000"))

    costo_esperado = notional * D("0.0024")  # 12 bps por lado, 24 round-trip
    assert costo_esperado == D("1.2")
    assert D("1000") - ledger.cash == costo_esperado
    assert ledger.cash == D("998.8")
    assert ledger.fees_total_usdt == D("1.0")  # 10 bps × 2 lados
    assert ledger.slippage_total_usdt == D("0.2")  # 2 bps × 2 lados
    assert ledger.realized_net_pnl_usdt == -costo_esperado


def test_cash_intermedio_refleja_la_fee_de_la_compra(ledger):
    ledger.record_buy(BTC, quantity=D("0.01"), price=D("50000"), grid_level=0)

    # 1000 − 500 (notional) − 0,50 (fee 10 bps) − 0,10 (slippage 2 bps)
    assert ledger.cash == D("499.4")


def test_cost_model_round_trip_es_24_bps():
    modelo = PaperCostModel()

    assert modelo.round_trip_bps == D("24")
    assert modelo.cost_bps_per_side("LIMIT") == D("12")
    assert modelo.fee_usdt(D("500"), "LIMIT") == D("0.5")
    assert modelo.slippage_usdt(D("500")) == D("0.1")


def test_slippage_es_obligatorio_y_no_puede_apagarse_silenciosamente():
    """I-6: sin slippage el cost_ratio sale sesgado a favor (desk §6.2)."""
    modelo = PaperCostModel()

    assert modelo.adverse_selection_bps == D("2")
    assert modelo.slippage_usdt(D("1000")) == D("0.2")
    with pytest.raises(ValueError):
        PaperCostModel(adverse_selection_bps=D("-1"))


# ---------------------------------------------------------------------------
# B11 / desk §3.1 — el inventario en contra baja el equity sin ciclo perdedor
# ---------------------------------------------------------------------------


def test_inventario_en_contra_baja_el_equity_sin_ciclo_perdedor(ledger):
    ledger.record_buy(BTC, quantity=D("0.01"), price=D("50000"), grid_level=0)

    equity_antes = ledger.mark_to_market({BTC: D("50000")})
    equity_despues = ledger.mark_to_market({BTC: D("45000")})

    assert equity_despues < equity_antes
    assert equity_antes - equity_despues == D("50")
    # Ningún ciclo cerrado, ningún PnL realizado negativo: la pérdida vive
    # íntegramente en el inventario. Medir sobre trades.profit_loss la ocultaría.
    assert ledger.closed_cycle_count == 0
    assert ledger.realized_gross_pnl_usdt == D("0")
    assert ledger.unrealized_pnl_usdt({BTC: D("45000")}) < D("0")


def test_grid_con_ciclo_ganador_y_equity_en_baja(ledger):
    """El modo de fallo del grid: ciclos ganadores y equity destruido."""
    ledger.record_buy(BTC, quantity=D("0.01"), price=D("50000"), grid_level=0)
    ledger.record_buy(BTC, quantity=D("0.01"), price=D("49000"), grid_level=1)
    # El nivel 0 cierra en ganancia (por construcción del grid)
    ledger.record_sell(BTC, quantity=D("0.01"), price=D("50500"))

    assert ledger.closed_cycle_count == 1
    assert ledger.realized_gross_pnl_usdt > D("0")

    # ...pero el inventario del nivel 1 quedó comprado arriba del mercado
    equity = ledger.mark_to_market({BTC: D("44000")})
    assert equity < D("1000")


def test_identidad_a4_equity_realizado_mas_no_realizado(ledger):
    # Cierre parcial de 1/3: fuerza una fracción no terminante en la asignación
    # de costos, que es donde una implementación con prorrateo ingenuo driftea.
    ledger.record_buy(BTC, quantity=D("0.015"), price=D("50000"), grid_level=0)
    ledger.record_sell(BTC, quantity=D("0.005"), price=D("50500"))
    precios = {BTC: D("47250.37")}

    equity = ledger.mark_to_market(precios)
    identidad = (
        ledger.realized_net_pnl_usdt + ledger.unrealized_pnl_usdt(precios) + D("1000")
    )

    # Gate A4 con tolerancia cero: la contabilidad cierra por los dos caminos.
    assert equity == identidad


def test_ratio_inventario_expone_spread_convertido_en_exposicion(ledger):
    """desk §3.1: |Δ pnl_no_realizado| / pnl_bruto_realizado, auditoría si > 80%."""
    ledger.record_buy(BTC, quantity=D("0.01"), price=D("50000"), grid_level=0)
    ledger.record_buy(BTC, quantity=D("0.01"), price=D("49000"), grid_level=1)
    ledger.record_sell(BTC, quantity=D("0.01"), price=D("50500"))

    precios = {BTC: D("44000")}
    bruto = ledger.realized_gross_pnl_usdt  # (50500 − 50000) × 0,01 = 5
    no_realizado = ledger.unrealized_pnl_usdt(precios)

    assert bruto == D("5")
    assert ledger.inventory_ratio(precios) == abs(no_realizado) / bruto
    # 0,01 BTC comprado a 49.000 marcado a 44.000 → el ratio dispara auditoría
    assert ledger.inventory_ratio(precios) > D("0.8")


def test_ratio_inventario_sin_pnl_bruto_es_indefinido(ledger):
    ledger.record_buy(BTC, quantity=D("0.01"), price=D("50000"), grid_level=0)

    assert ledger.inventory_ratio({BTC: D("45000")}) is None


# ---------------------------------------------------------------------------
# I-8 (BLOQUEANTE) — cycle_id y conteo de ciclos cerrados
# ---------------------------------------------------------------------------


def test_ciclo_emparejado_cuenta_uno_y_compra_sola_no_cuenta(ledger):
    compra = ledger.record_buy(BTC, quantity=D("0.01"), price=D("50000"), grid_level=0)
    assert ledger.closed_cycle_count == 0
    assert ledger.open_cycle_count == 1

    venta = ledger.record_sell(BTC, quantity=D("0.01"), price=D("50200"))
    assert venta.cycle_id == compra.cycle_id
    assert ledger.closed_cycle_count == 1
    assert ledger.open_cycle_count == 0

    ledger.record_buy(BTC, quantity=D("0.01"), price=D("49800"), grid_level=1)
    assert ledger.closed_cycle_count == 1  # la compra sin venta no cuenta
    assert ledger.open_cycle_count == 1


def test_venta_parcial_no_cierra_el_ciclo(ledger):
    ledger.record_buy(BTC, quantity=D("0.01"), price=D("50000"), grid_level=0)
    ledger.record_sell(BTC, quantity=D("0.004"), price=D("50200"))

    assert ledger.closed_cycle_count == 0
    assert ledger.open_cycle_count == 1
    assert ledger.position(BTC) == D("0.006")


def test_ciclos_se_cierran_fifo(ledger):
    c0 = ledger.record_buy(BTC, quantity=D("0.01"), price=D("50000"), grid_level=0)
    ledger.record_buy(BTC, quantity=D("0.01"), price=D("49000"), grid_level=1)

    venta = ledger.record_sell(BTC, quantity=D("0.01"), price=D("50500"))

    assert venta.cycle_id == c0.cycle_id
    assert ledger.closed_cycle_count == 1
    assert ledger.open_cycle_count == 1


def test_ciclo_cerrado_expone_economia_neta(ledger):
    ledger.record_buy(BTC, quantity=D("0.01"), price=D("50000"), grid_level=0)
    ledger.record_sell(BTC, quantity=D("0.01"), price=D("50500"))

    ciclo = ledger.closed_cycles()[0]
    assert ciclo.state == "closed"
    assert ciclo.grid_level == 0
    assert ciclo.gross_pnl_usdt == D("5")
    # 5 − fee compra 0,50 − slip 0,10 − fee venta 0,505 − slip 0,101
    assert ciclo.net_pnl_usdt == D("3.794")
    assert ciclo.net_pnl_usdt == (
        ciclo.gross_pnl_usdt - ciclo.fees_usdt - ciclo.slippage_usdt
    )


def test_venta_sin_inventario_falla_cerrado(ledger):
    with pytest.raises(InsufficientPaperInventory):
        ledger.record_sell(BTC, quantity=D("0.01"), price=D("50000"))


def test_cost_ratio_usa_pnl_bruto_realizado(ledger):
    ledger.record_buy(BTC, quantity=D("0.01"), price=D("50000"), grid_level=0)
    ledger.record_sell(BTC, quantity=D("0.01"), price=D("50500"))

    bruto = D("5")  # (50500 − 50000) × 0,01
    costos = ledger.fees_total_usdt + ledger.slippage_total_usdt

    assert ledger.realized_gross_pnl_usdt == bruto
    assert ledger.cost_ratio() == costos / bruto


# ---------------------------------------------------------------------------
# I-13 (BLOQUEANTE) — cierre diario anclado a 00:00 UTC y serie de retornos
# ---------------------------------------------------------------------------


def test_dos_snapshots_en_dias_distintos_dan_retorno_diario():
    series = PaperEquitySeries()
    dia1 = datetime(2026, 8, 15, 0, 0, 0, tzinfo=timezone.utc)
    dia2 = datetime(2026, 8, 16, 0, 0, 2, tzinfo=timezone.utc)

    series.record(D("1000"), at=dia1)
    series.record(D("1010"), at=dia2)

    cierres = series.daily_closes()
    assert [ts for ts, _ in cierres] == [
        dia1,
        datetime(2026, 8, 16, 0, 0, 0, tzinfo=timezone.utc),
    ]
    assert series.daily_returns() == [D("0.01")]


def test_snapshot_de_media_tarde_no_es_cierre_diario():
    series = PaperEquitySeries()
    medianoche = datetime(2026, 8, 15, 0, 0, 0, tzinfo=timezone.utc)

    series.record(D("1000"), at=medianoche)
    series.record(D("1200"), at=medianoche + timedelta(hours=12))

    assert len(series.samples) == 2
    assert len(series.daily_closes()) == 1
    assert series.daily_returns() == []


def test_cierre_diario_se_ancla_al_sample_mas_cercano_a_medianoche():
    series = PaperEquitySeries()
    medianoche = datetime(2026, 8, 16, 0, 0, 0, tzinfo=timezone.utc)

    series.record(D("999"), at=medianoche - timedelta(minutes=14))
    series.record(D("1000"), at=medianoche + timedelta(minutes=1))
    series.record(D("1001"), at=medianoche + timedelta(minutes=16))

    assert series.daily_closes() == [(medianoche, D("1000"))]


def test_daily_close_anchor_respeta_la_tolerancia():
    assert daily_close_anchor(
        datetime(2026, 8, 16, 0, 10, tzinfo=timezone.utc)
    ) == datetime(2026, 8, 16, 0, 0, tzinfo=timezone.utc)
    assert daily_close_anchor(
        datetime(2026, 8, 15, 23, 50, tzinfo=timezone.utc)
    ) == datetime(2026, 8, 16, 0, 0, tzinfo=timezone.utc)
    assert daily_close_anchor(datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc)) is None


def test_timestamp_naive_se_interpreta_como_utc():
    series = PaperEquitySeries()

    series.record(D("1000"), at=datetime(2026, 8, 15, 0, 0, 0))

    ts, _ = series.daily_closes()[0]
    assert ts == datetime(2026, 8, 15, 0, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# desk §3.3 — MaxDD sobre capital desplegado, no sobre el cap del book
# ---------------------------------------------------------------------------


def test_maxdd_se_reporta_sobre_capital_desplegado():
    series = PaperEquitySeries()
    base = datetime(2026, 8, 15, 0, 0, 0, tzinfo=timezone.utc)
    # Book Core: 560 asignados, 200 desplegados; el resto es USDT ocioso.
    for i, equity in enumerate(["560", "565", "550", "558"]):
        series.record(D(equity), at=base + timedelta(days=i), deployed_capital=D("200"))

    assert series.max_drawdown_usdt() == D("15")
    # 15 / 200 = 7,5% → ámbar. Diluido contra los 560 del book daría 2,7% (verde).
    assert series.max_drawdown_pct_deployed() == D("0.075")
    assert series.max_drawdown_pct_deployed() > series.max_drawdown()
    assert series.deployed_capital == D("200")


def test_maxdd_relativo_al_pico_sigue_disponible():
    series = PaperEquitySeries()
    base = datetime(2026, 8, 15, 0, 0, 0, tzinfo=timezone.utc)
    for i, equity in enumerate(["1000", "1100", "990", "1050"]):
        series.record(D(equity), at=base + timedelta(days=i), deployed_capital=D("200"))

    assert series.max_drawdown() == D("0.1")  # 990/1100 − 1


def test_deployed_capital_viaja_en_el_snapshot():
    ledger = PaperEquityLedger(initial_cash=D("1000"), deployed_capital=D("200"))
    feed = FakeMarkPriceFeed({BTC: "50000"})
    series = PaperEquitySeries()
    ledger.record_buy(BTC, quantity=D("0.001"), price=D("50000"), grid_level=0)

    compute_paper_portfolio_value(ledger=ledger, price_feed=feed, series=series)

    muestra = series.samples[-1]
    assert muestra["deployed_capital"] == "200"
    assert muestra["cash"] == str(ledger.cash)
    assert muestra["inventory_value"] == "50"


def test_mtm_persiste_ledger_con_fees_y_slippage(tmp_path, monkeypatch):
    """C3 / Celery: el path MtM debe dejar fees/slippage en disco, no solo la serie.

    Sin fills el autosave de buys no corre: el snapshot paper tiene que persistir
    el ledger (cost_model + acumulados) para que el tick E2E sea auditable.
    El config_hash del sample sale de resolve() (no del header sticky).
    """
    monkeypatch.setenv("GRID_CONFIG_HASH", "hash-congelado")
    ledger_path = tmp_path / "paper_equity_ledger.json"
    series_path = tmp_path / "paper_equity_series.json"
    ledger = PaperEquityLedger(
        initial_cash=D("1000"),
        deployed_capital=D("200"),
        storage_path=ledger_path,
    )
    series = PaperEquitySeries(config_hash="hash-viejo-sticky", storage_path=series_path)

    assert not ledger_path.exists()
    compute_paper_portfolio_value(ledger=ledger, price_feed=FakeMarkPriceFeed({}), series=series)

    assert ledger_path.exists()
    recuperado = PaperEquityLedger.load(ledger_path)
    payload = recuperado.to_dict()
    assert recuperado.deployed_capital == D("200")
    assert payload["fees_total_usdt"] == "0"
    assert payload["slippage_total_usdt"] == "0"
    assert recuperado.cost_model.round_trip_bps == D("24")
    assert payload["cost_model"]["maker_fee_bps"] == "10"
    assert payload["cost_model"]["adverse_selection_bps"] == "2"
    assert series_path.exists()
    sample = PaperEquitySeries.load(series_path).samples[-1]
    assert sample["config_hash"] == "hash-congelado"
    assert sample["deployed_capital"] == "200"


# ---------------------------------------------------------------------------
# I-12 (BLOQUEANTE) — config_hash: el freeze deja de ser palabra contra palabra
# ---------------------------------------------------------------------------


def test_config_hash_es_determinista_e_independiente_del_orden():
    revuelta = dict(reversed(list(CONFIG_VENTANA.items())))

    assert compute_config_hash(CONFIG_VENTANA) == compute_config_hash(CONFIG_VENTANA)
    assert compute_config_hash(revuelta) == compute_config_hash(CONFIG_VENTANA)
    assert len(compute_config_hash(CONFIG_VENTANA)) == 64  # sha256 hex


def test_cambiar_el_spacing_cambia_el_config_hash():
    """A1: cambiar spacing dentro de la ventana debe ser detectable (N11)."""
    tuneada = {**CONFIG_VENTANA, "spacing_bps": 40}

    assert compute_config_hash(tuneada) != compute_config_hash(CONFIG_VENTANA)


def test_config_hash_ignora_secrets():
    con_secrets = {
        **CONFIG_VENTANA,
        "binance_api_key": "AKIA-no-va-al-hash",
        "api_secret": "tampoco",
        "telegram_token": "ni-esto",
    }

    assert compute_config_hash(con_secrets) == compute_config_hash(CONFIG_VENTANA)
    assert "AKIA" not in compute_config_hash(con_secrets)


def test_config_hash_se_persiste_en_cada_marca_de_equity(ledger, monkeypatch):
    esperado = compute_config_hash(CONFIG_VENTANA)
    monkeypatch.setenv("GRID_CONFIG_HASH", esperado)
    feed = FakeMarkPriceFeed({BTC: "50000"})
    # Header sticky distinto a propósito: el sample debe usar resolve().
    series = PaperEquitySeries(config_hash="hash-sticky-incorrecto")
    ledger.record_buy(BTC, quantity=D("0.001"), price=D("50000"), grid_level=0)

    compute_paper_portfolio_value(ledger=ledger, price_feed=feed, series=series)

    assert series.samples[-1]["config_hash"] == esperado
    assert esperado in series.config_hashes()
    assert "hash-sticky-incorrecto" not in {
        s["config_hash"] for s in series.samples if s.get("config_hash")
    }


def test_config_hash_se_resuelve_del_archivo_de_config_del_bot(tmp_path, monkeypatch):
    """El freeze no depende de que alguien recuerde exportar una variable."""
    destino = tmp_path / "grid_config_optimized.json"
    destino.write_text(json.dumps(CONFIG_VENTANA), encoding="utf-8")
    monkeypatch.delenv("GRID_CONFIG_HASH", raising=False)
    monkeypatch.setenv("GRID_CONFIG_FILE", str(destino))

    assert resolve_grid_config_hash() == compute_config_hash(CONFIG_VENTANA)


def test_config_hash_explicito_del_desk_tiene_prioridad(tmp_path, monkeypatch):
    monkeypatch.setenv("GRID_CONFIG_HASH", "hash-congelado-por-el-desk")
    monkeypatch.setenv("GRID_CONFIG_FILE", str(tmp_path / "no-existe.json"))

    assert resolve_grid_config_hash() == "hash-congelado-por-el-desk"


def test_sin_config_legible_no_hay_hash_inventado(tmp_path, monkeypatch):
    monkeypatch.delenv("GRID_CONFIG_HASH", raising=False)
    monkeypatch.setenv("GRID_CONFIG_FILE", str(tmp_path / "no-existe.json"))

    # Falla cerrado: sin hash el gate A1 no se puede firmar, que es lo correcto.
    assert resolve_grid_config_hash() is None


def test_series_detecta_cambio_de_config_dentro_de_la_ventana(monkeypatch):
    monkeypatch.setenv("GRID_CONFIG_HASH", "hash-congelado")
    series = PaperEquitySeries(config_hash="hash-congelado")
    base = datetime(2026, 8, 15, 0, 0, 0, tzinfo=timezone.utc)

    series.record(D("560"), at=base)
    assert series.config_is_frozen() is True
    assert series.config_is_frozen(expected_hash="hash-congelado") is True
    assert series.config_is_frozen(expected_hash="otro") is False

    series.record(D("561"), at=base + timedelta(days=1), config_hash="hash-tuneado")
    assert series.config_is_frozen() is False
    assert series.config_hashes() == {"hash-congelado", "hash-tuneado"}


def test_config_is_frozen_fail_closed_sin_expected(monkeypatch):
    monkeypatch.delenv("GRID_CONFIG_HASH", raising=False)
    monkeypatch.setenv("GRID_CONFIG_FILE", "/tmp/no-existe-grid-config-a1.json")
    series = PaperEquitySeries(config_hash="solo-uno")
    series.record(D("1000"), at=datetime(2026, 8, 15, tzinfo=timezone.utc))
    assert series.config_is_frozen() is False


def test_config_is_frozen_sticky_distinto_al_expected(monkeypatch):
    sticky = "ac1cb59676abbaa42a9e1409809ee3b7009ae5114e15055615a7a1ff63b4b219"
    expected = "ff6a35fcf84bf91c1da9ea81116265a3789f1d85e5456d19622897c82ed7f5c4"
    monkeypatch.setenv("GRID_CONFIG_HASH", expected)
    series = PaperEquitySeries(config_hash=sticky)
    series.record(
        D("1000"),
        at=datetime(2026, 8, 26, 12, 11, tzinfo=timezone.utc),
        config_hash=sticky,
    )
    assert series.config_is_frozen() is False
    assert series.config_is_frozen(expected_hash=expected) is False
    assert series.config_is_frozen(expected_hash=sticky) is True


# ---------------------------------------------------------------------------
# Regla 10-financial-integrity — Decimal en todo el dinero, floats rechazados
# ---------------------------------------------------------------------------


def test_todo_el_dinero_es_decimal(ledger):
    fill = ledger.record_buy(BTC, quantity=D("0.01"), price=D("50000"), grid_level=0)

    for valor in (
        ledger.cash,
        ledger.initial_cash,
        ledger.deployed_capital,
        ledger.fees_total_usdt,
        ledger.slippage_total_usdt,
        ledger.realized_gross_pnl_usdt,
        ledger.realized_net_pnl_usdt,
        ledger.position(BTC),
        ledger.mark_to_market({BTC: D("50000")}),
        fill.quantity,
        fill.price,
        fill.notional_usdt,
        fill.commission,
        fill.commission_usdt,
        fill.slippage_usdt,
    ):
        assert isinstance(valor, Decimal)


def test_los_floats_se_rechazan_en_dinero(ledger):
    with pytest.raises(TypeError):
        ledger.record_buy(BTC, quantity=D("0.01"), price=50000.0)
    with pytest.raises(TypeError):
        ledger.record_buy(BTC, quantity=0.01, price=D("50000"))
    with pytest.raises(TypeError):
        PaperEquityLedger(initial_cash=1000.0)

    ledger.record_buy(BTC, quantity=D("0.01"), price=D("50000"), grid_level=0)
    with pytest.raises(TypeError):
        ledger.mark_to_market({BTC: 45000.0})


def test_la_serie_tambien_rechaza_floats():
    series = PaperEquitySeries()

    with pytest.raises(TypeError):
        series.record(1000.0, at=datetime(2026, 8, 15, tzinfo=timezone.utc))


# ---------------------------------------------------------------------------
# I-1 / I-2 — persistencia versionada en JSON (sin migraciones Alembic)
# ---------------------------------------------------------------------------


def test_ledger_round_trip_json_preserva_decimales(tmp_path, ledger):
    ledger.record_buy(BTC, quantity=D("0.01"), price=D("50000"), grid_level=0)
    ledger.record_sell(BTC, quantity=D("0.01"), price=D("50500"))
    destino = tmp_path / "paper_equity_ledger.json"

    ledger.save(destino)
    recuperado = PaperEquityLedger.load(destino)

    assert recuperado.to_dict()["schema_version"] == SCHEMA_VERSION
    assert recuperado.cash == ledger.cash
    assert recuperado.deployed_capital == ledger.deployed_capital
    assert recuperado.fees_total_usdt == ledger.fees_total_usdt
    assert recuperado.slippage_total_usdt == ledger.slippage_total_usdt
    assert recuperado.realized_gross_pnl_usdt == ledger.realized_gross_pnl_usdt
    assert recuperado.closed_cycle_count == ledger.closed_cycle_count
    assert recuperado.mark_to_market({BTC: D("50500")}) == ledger.mark_to_market(
        {BTC: D("50500")}
    )


def test_los_fills_persisten_comision_por_trade(ledger):
    """Gate A5 sin tocar Alembic: fee atribuida por fill, en el JSON del ledger."""
    ledger.record_buy(BTC, quantity=D("0.01"), price=D("50000"), grid_level=0)
    payload = ledger.to_dict()

    fill = payload["fills"][0]
    assert fill["commission"] == "0.5"
    assert fill["commission_asset"] == "USDT"
    assert fill["commission_usdt"] == "0.5"
    assert fill["slippage_usdt"] == "0.1"
    assert fill["cycle_id"]
    assert fill["grid_level"] == 0


def test_serie_round_trip_json(tmp_path, monkeypatch):
    monkeypatch.setenv("GRID_CONFIG_HASH", "hash-congelado")
    series = PaperEquitySeries(config_hash="hash-congelado")
    base = datetime(2026, 8, 15, 0, 0, 0, tzinfo=timezone.utc)
    series.record(D("1000"), at=base, deployed_capital=D("200"))
    series.record(D("1010"), at=base + timedelta(days=1), deployed_capital=D("200"))
    destino = tmp_path / "paper_equity_series.json"

    series.save(destino)
    recuperada = PaperEquitySeries.load(destino)

    assert recuperada.to_dict()["schema_version"] == SCHEMA_VERSION
    assert recuperada.daily_returns() == [D("0.01")]
    assert recuperada.deployed_capital == D("200")
    assert recuperada.config_is_frozen() is True


# ---------------------------------------------------------------------------
# A2 — cobertura de la serie (gaps > 2 h invalidan el MaxDD)
# ---------------------------------------------------------------------------


def test_coverage_detecta_gaps_en_la_serie():
    series = PaperEquitySeries()
    base = datetime(2026, 8, 15, 0, 0, 0, tzinfo=timezone.utc)

    series.record(D("560"), at=base)
    series.record(D("561"), at=base + timedelta(minutes=15))
    series.record(D("562"), at=base + timedelta(hours=4))

    cobertura = series.coverage()
    assert cobertura["samples"] == 3
    assert cobertura["max_gap_seconds"] == 3 * 3600 + 45 * 60
    assert cobertura["daily_closes"] == 1


# ---------------------------------------------------------------------------
# I-4 — BinanceService en simulación consume el ledger, no constantes
# ---------------------------------------------------------------------------


class _FakeTickerClient:
    def __init__(self, price="61234.56"):
        self.price = price

    def get_symbol_ticker(self, symbol: str):
        return {"symbol": symbol, "price": self.price}


def test_precio_simulado_sale_del_ticker_no_de_una_constante():
    from app.services.binance_service import BinanceService

    svc = BinanceService.__new__(BinanceService)
    svc.client = _FakeTickerClient("61234.56")

    assert svc._get_simulated_price(BTC) == pytest.approx(61234.56)


def test_precio_simulado_falla_cerrado_sin_ticker():
    from app.services.binance_service import BinanceService

    class _Roto:
        def get_symbol_ticker(self, symbol: str):
            raise RuntimeError("ticker caído")

    svc = BinanceService.__new__(BinanceService)
    svc.client = _Roto()

    with pytest.raises(MarkPriceUnavailable):
        svc._get_simulated_price(BTC)


def test_account_info_simulada_refleja_el_ledger():
    from app.services.binance_service import BinanceService

    ledger = PaperEquityLedger(initial_cash=D("560"), deployed_capital=D("200"))
    ledger.record_buy(BTC, quantity=D("0.002"), price=D("50000"), grid_level=0)

    svc = BinanceService.__new__(BinanceService)
    svc.client = _FakeTickerClient()
    info = svc._get_simulated_account_info(ledger=ledger)

    balances = {b["asset"]: b["free"] for b in info["balances"]}
    assert D(balances["USDT"]) == ledger.cash
    assert D(balances["BTC"]) == D("0.002")
    # Los balances fijos históricos (1000 USDT / 0,01 BTC / 0,1 ETH) ya no existen.
    assert D(balances["USDT"]) != D("1000")
    assert "ETH" not in balances
    assert info["makerCommission"] == 10
