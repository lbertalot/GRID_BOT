"""TDD — helper paper-only para resetear la ventana L0 (próximo T0).

Usa `tmp_path`: no toca `paper_telemetry/` de ops, no Redis, no live.
PROMOTE_LIVE: NO.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

from app.core.paper_equity_ledger import PaperEquityLedger, PaperEquitySeries
from scripts.reset_paper_l0_window import (
    SI_N10_NOTE,
    TELEMETRY_BASENAMES,
    main,
    reset_paper_l0_window,
)

D = Decimal

LEDGER_NAME = "paper_equity_ledger.json"
SERIES_NAME = "paper_equity_series.json"
SNAPSHOT_NAME = "last_portfolio_snapshot.json"


def _write_dirty_telemetry(telemetry: Path) -> None:
    """Simula una ventana previa con fills/samples (solo tmp_path)."""
    telemetry.mkdir(parents=True, exist_ok=True)
    ledger = PaperEquityLedger(
        initial_cash=D("560"),
        deployed_capital=D("200"),
        storage_path=telemetry / LEDGER_NAME,
    )
    ledger.record_buy(
        "ETHUSDT",
        quantity=D("0.01"),
        price=D("3500"),
        grid_level=0,
    )
    ledger.save()
    series = PaperEquitySeries(
        config_hash="hash-ventana-vieja",
        deployed_capital=D("200"),
        storage_path=telemetry / SERIES_NAME,
    )
    series.record(
        D("979"),
        cash=ledger.cash,
        inventory_value=D("35"),
        deployed_capital=D("200"),
    )
    (telemetry / SNAPSHOT_NAME).write_text(
        json.dumps({"equity": "979", "stale": True}),
        encoding="utf-8",
    )


def test_archiva_y_escribe_ledger_l0_decimal(tmp_path: Path) -> None:
    """Copia SoT previa y deja ledger nuevo E0=1000 / deployed=200 / 10+2 bps."""
    telemetry = tmp_path / "tel"
    archive = tmp_path / "arch"
    _write_dirty_telemetry(telemetry)

    result = reset_paper_l0_window(
        telemetry_dir=telemetry,
        archive_dir=archive,
        config_hash="hash-nuevo-t0",
    )

    assert result["dry_run"] is False
    assert result["promote_live"] == "NO"
    assert set(result["archived"]) == set(TELEMETRY_BASENAMES)

    old = json.loads((archive / LEDGER_NAME).read_text(encoding="utf-8"))
    assert old["initial_cash"] == "560"
    assert len(old["fills"]) == 1
    assert json.loads((archive / SNAPSHOT_NAME).read_text(encoding="utf-8"))["stale"] is True

    ledger = PaperEquityLedger.load(telemetry / LEDGER_NAME)
    assert ledger.initial_cash == D("1000")
    assert ledger.cash == D("1000")
    assert ledger.deployed_capital == D("200")
    assert ledger.cycles == ()
    assert ledger.fills == ()
    assert ledger.cost_model.maker_fee_bps == D("10")
    assert ledger.cost_model.adverse_selection_bps == D("2")
    assert ledger.cost_model.round_trip_bps == D("24")

    series = PaperEquitySeries.load(telemetry / SERIES_NAME)
    assert series.config_hash == "hash-nuevo-t0"
    assert series.samples == []
    assert series.deployed_capital == D("200")


def test_archiva_solo_archivos_existentes(tmp_path: Path) -> None:
    telemetry = tmp_path / "tel"
    archive = tmp_path / "arch"
    telemetry.mkdir()
    PaperEquityLedger(
        initial_cash=D("1000"),
        deployed_capital=D("200"),
        storage_path=telemetry / LEDGER_NAME,
    ).save()

    result = reset_paper_l0_window(
        telemetry_dir=telemetry,
        archive_dir=archive,
        config_hash="h",
    )

    assert result["archived"] == [LEDGER_NAME]
    assert (archive / LEDGER_NAME).is_file()
    assert not (archive / SERIES_NAME).exists()
    assert not (archive / SNAPSHOT_NAME).exists()
    assert (telemetry / SERIES_NAME).is_file()


def test_sin_archivos_previos_igual_escribe_l0(tmp_path: Path) -> None:
    telemetry = tmp_path / "tel"
    archive = tmp_path / "arch"

    result = reset_paper_l0_window(
        telemetry_dir=telemetry,
        archive_dir=archive,
        config_hash="h",
    )

    assert result["archived"] == []
    assert archive.is_dir()
    ledger = PaperEquityLedger.load(telemetry / LEDGER_NAME)
    assert ledger.cash == D("1000")
    assert PaperEquitySeries.load(telemetry / SERIES_NAME).samples == []


def test_usa_resolve_grid_config_hash_si_no_se_pasa(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        "scripts.reset_paper_l0_window.resolve_grid_config_hash",
        lambda: "hash-desde-resolve",
    )
    telemetry = tmp_path / "tel"
    result = reset_paper_l0_window(
        telemetry_dir=telemetry,
        archive_dir=tmp_path / "arch",
    )
    assert result["config_hash"] == "hash-desde-resolve"
    assert (
        PaperEquitySeries.load(telemetry / SERIES_NAME).config_hash
        == "hash-desde-resolve"
    )


def test_seed_e0_opcional_un_sample_1000(tmp_path: Path) -> None:
    telemetry = tmp_path / "tel"
    reset_paper_l0_window(
        telemetry_dir=telemetry,
        archive_dir=tmp_path / "arch",
        config_hash="h-e0",
        seed_e0_sample=True,
    )
    series = PaperEquitySeries.load(telemetry / SERIES_NAME)
    assert len(series.samples) == 1
    sample = series.samples[0]
    assert D(sample["equity"]) == D("1000")
    assert D(sample["cash"]) == D("1000")
    assert sample["config_hash"] == "h-e0"


def test_dry_run_no_escribe(tmp_path: Path) -> None:
    telemetry = tmp_path / "tel"
    archive = tmp_path / "arch"
    _write_dirty_telemetry(telemetry)
    before = (telemetry / LEDGER_NAME).read_text(encoding="utf-8")

    result = reset_paper_l0_window(
        telemetry_dir=telemetry,
        archive_dir=archive,
        config_hash="no-debe-persistir",
        dry_run=True,
        seed_e0_sample=True,
        reset_process_singletons=True,
        reset_si_for_new_window=True,
        breakers=MagicMock(),
    )

    assert result["dry_run"] is True
    assert result["would_archive"] == list(TELEMETRY_BASENAMES)
    assert not archive.exists()
    assert (telemetry / LEDGER_NAME).read_text(encoding="utf-8") == before
    assert json.loads(before)["initial_cash"] == "560"


def test_no_resetea_singletons_salvo_flag(tmp_path: Path, monkeypatch) -> None:
    called = {"n": 0}

    def _fake_reset() -> None:
        called["n"] += 1

    monkeypatch.setattr(
        "scripts.reset_paper_l0_window.reset_paper_telemetry",
        _fake_reset,
    )
    reset_paper_l0_window(
        telemetry_dir=tmp_path / "tel",
        archive_dir=tmp_path / "arch",
        config_hash="h",
    )
    assert called["n"] == 0

    reset_paper_l0_window(
        telemetry_dir=tmp_path / "tel2",
        archive_dir=tmp_path / "arch2",
        config_hash="h",
        reset_process_singletons=True,
    )
    assert called["n"] == 1


def test_system_integrity_queda_intacto_por_defecto(tmp_path: Path) -> None:
    breakers = MagicMock()
    result = reset_paper_l0_window(
        telemetry_dir=tmp_path / "tel",
        archive_dir=tmp_path / "arch",
        config_hash="h",
        breakers=breakers,
    )
    breakers.deactivate_breaker.assert_not_called()
    assert result["reset_si_for_new_window"] is False
    assert result["si_action"] == "skipped"
    assert "AS-10" in result["si_note"]
    assert "N10" in result["si_note"]


def test_reset_si_es_n10_no_as10_con_breakers_mock(tmp_path: Path) -> None:
    """Flag explícito: N10 restart de ventana. Tests no pegan Redis."""
    breakers = MagicMock()
    breakers.deactivate_breaker = MagicMock(return_value=True)

    result = reset_paper_l0_window(
        telemetry_dir=tmp_path / "tel",
        archive_dir=tmp_path / "arch",
        config_hash="h",
        reset_si_for_new_window=True,
        breakers=breakers,
    )

    breakers.deactivate_breaker.assert_called_once_with("system_integrity")
    assert result["reset_si_for_new_window"] is True
    assert result["si_action"] == "deactivated"
    assert result["si_note"] == SI_N10_NOTE
    assert "no es AS-10" in SI_N10_NOTE.lower() or "No es AS-10" in SI_N10_NOTE


def test_reset_si_sin_breakers_inyectados_falla_cerrado(tmp_path: Path) -> None:
    """Sin mock no se abre Redis: fail-closed."""
    try:
        reset_paper_l0_window(
            telemetry_dir=tmp_path / "tel",
            archive_dir=tmp_path / "arch",
            config_hash="h",
            reset_si_for_new_window=True,
        )
    except ValueError as exc:
        assert "breakers" in str(exc).lower()
        assert "N10" in str(exc)
        return
    raise AssertionError("debía fallar cerrado sin breakers inyectado")


def test_cli_dry_run_no_escribe(tmp_path: Path) -> None:
    telemetry = tmp_path / "tel"
    archive = tmp_path / "arch"
    _write_dirty_telemetry(telemetry)
    before = (telemetry / LEDGER_NAME).read_text(encoding="utf-8")

    rc = main(
        [
            "--telemetry-dir",
            str(telemetry),
            "--archive-dir",
            str(archive),
            "--dry-run",
            "--config-hash",
            "cli-dry",
        ]
    )

    assert rc == 0
    assert not archive.exists()
    assert (telemetry / LEDGER_NAME).read_text(encoding="utf-8") == before


def test_cli_escribe_en_tmp(tmp_path: Path) -> None:
    telemetry = tmp_path / "tel"
    archive = tmp_path / "arch"
    _write_dirty_telemetry(telemetry)

    rc = main(
        [
            "--telemetry-dir",
            str(telemetry),
            "--archive-dir",
            str(archive),
            "--config-hash",
            "cli-write",
        ]
    )

    assert rc == 0
    ledger = PaperEquityLedger.load(telemetry / LEDGER_NAME)
    assert ledger.initial_cash == D("1000")
    assert ledger.cash == D("1000")
    assert (archive / LEDGER_NAME).is_file()
