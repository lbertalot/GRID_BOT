"""E3 bonus — gauges Prometheus paper-aware (mode, equity, snapshot, pipeline).

Hotfix: hidratar portfolio_snapshot_last_unixtime en el proceso API
(sidecar / DB) cuando scrape llama publish_obs_gauges() sin unixtime.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def test_publish_obs_gauges_sets_mode_and_equity(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("PAPER_TRADING", "true")
    monkeypatch.setenv("FORCE_REAL_MODE", "false")
    monkeypatch.setenv("TRADING_ENABLED", "false")
    monkeypatch.setenv("PAPER_TELEMETRY_DIR", str(tmp_path))

    series = tmp_path / "paper_equity_series.json"
    series.write_text(
        '{"schema_version":1,"samples":[{"at":"2026-08-06T12:00:00+00:00","equity":"1000.00"}]}',
        encoding="utf-8",
    )

    from app.core.obs_gauges import publish_obs_gauges
    from app.core import metrics as m

    with (
        patch.object(m.trading_effective_mode, "labels") as mode_labels,
        patch.object(m.paper_equity_usdt, "set") as equity_set,
        patch.object(m.paper_equity_samples, "set") as samples_set,
        patch.object(m.portfolio_snapshot_last_unixtime, "set") as snap_set,
    ):
        mode_gauge = mode_labels.return_value
        publish_obs_gauges(snapshot_unixtime=1722945600.0)

    mode_labels.assert_any_call(mode="paper")
    mode_gauge.set.assert_called()
    equity_set.assert_called()
    assert float(equity_set.call_args[0][0]) == 1000.0
    samples_set.assert_called_with(1)
    snap_set.assert_called_with(1722945600.0)


def test_binance_api_errors_counter_exists():
    from app.core.metrics import binance_api_errors_total

    # Path fácil: counter ya cableado en binance_client_singleton
    # prometheus_client guarda el nombre sin sufijo _total en ._name
    assert "binance_api_errors" in binance_api_errors_total._name
    assert "code" in binance_api_errors_total._labelnames
    assert "phase" in binance_api_errors_total._labelnames


def test_explicit_snapshot_writes_sidecar_and_sets_gauge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PAPER_TRADING", "true")
    monkeypatch.setenv("FORCE_REAL_MODE", "false")
    monkeypatch.setenv("TRADING_ENABLED", "false")
    monkeypatch.setenv("PAPER_TELEMETRY_DIR", str(tmp_path))

    from app.core import metrics as m
    from app.core.obs_gauges import publish_obs_gauges

    ts = 1722945600.0
    with patch.object(m.portfolio_snapshot_last_unixtime, "set") as snap_set:
        publish_obs_gauges(snapshot_unixtime=ts)

    snap_set.assert_called_with(ts)
    sidecar = tmp_path / "last_portfolio_snapshot.json"
    assert sidecar.is_file()
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    assert float(payload["captured_at_unix"]) == ts


def test_hydrate_from_sidecar_when_unixtime_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PAPER_TRADING", "true")
    monkeypatch.setenv("FORCE_REAL_MODE", "false")
    monkeypatch.setenv("TRADING_ENABLED", "false")
    monkeypatch.setenv("PAPER_TELEMETRY_DIR", str(tmp_path))
    monkeypatch.setenv("OBS_SNAPSHOT_SIDECAR_MAX_AGE_SEC", "3600")

    fresh_ts = time.time() - 60.0
    (tmp_path / "last_portfolio_snapshot.json").write_text(
        json.dumps({"captured_at_unix": fresh_ts}),
        encoding="utf-8",
    )

    from app.core import metrics as m
    from app.core.obs_gauges import publish_obs_gauges

    with (
        patch.object(m.portfolio_snapshot_last_unixtime, "set") as snap_set,
        patch("app.core.obs_gauges._hydrate_snapshot_from_db") as db_hydrate,
    ):
        publish_obs_gauges()

    snap_set.assert_called_once()
    assert abs(float(snap_set.call_args[0][0]) - fresh_ts) < 1e-6
    db_hydrate.assert_not_called()


def test_hydrate_from_db_when_sidecar_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PAPER_TRADING", "true")
    monkeypatch.setenv("FORCE_REAL_MODE", "false")
    monkeypatch.setenv("TRADING_ENABLED", "false")
    monkeypatch.setenv("PAPER_TELEMETRY_DIR", str(tmp_path))

    captured = datetime(2026, 8, 6, 14, 0, 0, tzinfo=timezone.utc)
    expected = captured.timestamp()

    db = MagicMock()
    result = MagicMock()
    result.fetchone.return_value = (captured,)
    db.execute.return_value = result

    from app.core import metrics as m
    from app.core.obs_gauges import publish_obs_gauges

    with (
        patch.object(m.portfolio_snapshot_last_unixtime, "set") as snap_set,
        patch("app.db.session.SessionLocal", return_value=db),
    ):
        publish_obs_gauges()

    snap_set.assert_called_once_with(expected)
    db.close.assert_called_once()


def test_hydrate_db_fail_soft_does_not_set_gauge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PAPER_TRADING", "true")
    monkeypatch.setenv("FORCE_REAL_MODE", "false")
    monkeypatch.setenv("TRADING_ENABLED", "false")
    monkeypatch.setenv("PAPER_TELEMETRY_DIR", str(tmp_path))

    from app.core import metrics as m
    from app.core.obs_gauges import publish_obs_gauges

    with (
        patch.object(m.portfolio_snapshot_last_unixtime, "set") as snap_set,
        patch(
            "app.db.session.SessionLocal",
            side_effect=RuntimeError("db down"),
        ),
    ):
        publish_obs_gauges()  # no debe propagar

    snap_set.assert_not_called()


def test_explicit_unixtime_not_overridden_by_sidecar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PAPER_TRADING", "true")
    monkeypatch.setenv("FORCE_REAL_MODE", "false")
    monkeypatch.setenv("TRADING_ENABLED", "false")
    monkeypatch.setenv("PAPER_TELEMETRY_DIR", str(tmp_path))

    (tmp_path / "last_portfolio_snapshot.json").write_text(
        json.dumps({"captured_at_unix": 1111.0}),
        encoding="utf-8",
    )

    from app.core import metrics as m
    from app.core.obs_gauges import publish_obs_gauges

    with (
        patch.object(m.portfolio_snapshot_last_unixtime, "set") as snap_set,
        patch("app.core.obs_gauges._hydrate_snapshot_from_db") as db_hydrate,
    ):
        publish_obs_gauges(snapshot_unixtime=2222.0)

    snap_set.assert_called_once_with(2222.0)
    db_hydrate.assert_not_called()
    payload = json.loads(
        (tmp_path / "last_portfolio_snapshot.json").read_text(encoding="utf-8")
    )
    assert float(payload["captured_at_unix"]) == 2222.0


def test_stale_sidecar_falls_through_to_db(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PAPER_TRADING", "true")
    monkeypatch.setenv("FORCE_REAL_MODE", "false")
    monkeypatch.setenv("TRADING_ENABLED", "false")
    monkeypatch.setenv("PAPER_TELEMETRY_DIR", str(tmp_path))
    monkeypatch.setenv("OBS_SNAPSHOT_SIDECAR_MAX_AGE_SEC", "120")

    stale_ts = time.time() - 600.0
    (tmp_path / "last_portfolio_snapshot.json").write_text(
        json.dumps({"captured_at_unix": stale_ts}),
        encoding="utf-8",
    )

    from app.core import metrics as m
    from app.core.obs_gauges import publish_obs_gauges

    with (
        patch.object(m.portfolio_snapshot_last_unixtime, "set") as snap_set,
        patch(
            "app.core.obs_gauges._hydrate_snapshot_from_db",
            return_value=9999.0,
        ) as db_hydrate,
    ):
        publish_obs_gauges()

    db_hydrate.assert_called_once()
    snap_set.assert_called_once_with(9999.0)
