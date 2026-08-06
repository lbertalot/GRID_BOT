"""E4 — PipelineHealth paper-aware: idle paper no debe degradar por trades/balances=0."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.services import pipeline_health_tasks as ph


@pytest.fixture
def reports_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(ph, "REPORTS_DIR", tmp_path)
    return tmp_path


def _fake_session_with_fresh_snapshot(captured_at: datetime) -> MagicMock:
    db = MagicMock()

    def execute(sql, params=None):  # noqa: ANN001
        text_sql = str(sql)
        result = MagicMock()
        if "portfolio_snapshots" in text_sql and "MAX(captured_at)" in text_sql:
            result.fetchone.return_value = (captured_at,)
        else:
            result.fetchone.return_value = (None,)
            result.fetchall.return_value = []
        return result

    db.execute.side_effect = execute
    return db


def test_paper_idle_zero_writes_not_degraded(
    reports_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """PAPER_TRADING=true + increase==0 en trades/balances/perf → status ok (info)."""
    monkeypatch.setenv("PAPER_TRADING", "true")
    monkeypatch.setattr(ph, "ALERTS_SOFT_ONLY", True)

    now = datetime.now(timezone.utc)
    fresh = now - timedelta(minutes=5)

    with (
        patch.object(ph, "_check_table_prometheus", return_value=0.0),
        patch.object(
            ph, "SessionLocal", return_value=_fake_session_with_fresh_snapshot(fresh)
        ),
        patch("app.core.obs_gauges.publish_obs_gauges"),
    ):
        result = ph.check_pipeline_db_writes.run()

    assert result["ok"] is True
    assert result["status"] == "ok"
    assert result.get("paper_aware") is True
    soft = result.get("soft_failures") or []
    assert any("trades" in f for f in soft)
    assert any("balances" in f for f in soft)
    assert any("performance_metrics" in f for f in soft)


def test_paper_stale_snapshot_still_degraded(
    reports_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Paper-aware no silencia portfolio_snapshots viejos."""
    monkeypatch.setenv("PAPER_TRADING", "true")
    now = datetime.now(timezone.utc)
    stale = now - timedelta(minutes=120)

    with (
        patch.object(ph, "_check_table_prometheus", return_value=0.0),
        patch.object(
            ph, "SessionLocal", return_value=_fake_session_with_fresh_snapshot(stale)
        ),
        patch("app.core.obs_gauges.publish_obs_gauges"),
    ):
        result = ph.check_pipeline_db_writes.run()

    assert result["ok"] is False
    assert result["status"] == "degraded"
    assert any("portfolio_snapshots" in f for f in result["failures"])


def test_non_paper_zero_writes_degraded(
    reports_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sin paper, increase==0 sigue siendo hard failure."""
    monkeypatch.setenv("PAPER_TRADING", "false")
    monkeypatch.setenv("FORCE_REAL_MODE", "false")
    now = datetime.now(timezone.utc)
    fresh = now - timedelta(minutes=5)

    with (
        patch.object(ph, "_check_table_prometheus", return_value=0.0),
        patch.object(
            ph, "SessionLocal", return_value=_fake_session_with_fresh_snapshot(fresh)
        ),
        patch("app.core.obs_gauges.publish_obs_gauges"),
    ):
        result = ph.check_pipeline_db_writes.run()

    assert result["ok"] is False
    assert result["status"] == "degraded"
    assert any("trades" in f for f in result["failures"])
