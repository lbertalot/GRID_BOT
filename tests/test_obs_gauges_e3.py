"""E3 bonus — gauges Prometheus paper-aware (mode, equity, snapshot, pipeline)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

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
