"""Tests ligeros del watchdog de ingesta (Prometheus + reportes)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.services import pipeline_health_tasks as ph


def test_prom_query_parses_scalar_vector() -> None:
    sample = {
        "status": "success",
        "data": {
            "resultType": "vector",
            "result": [{"metric": {}, "value": [1700000000, "12.25"]}],
        },
    }
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(sample).encode("utf-8")
    mock_resp.__enter__ = lambda self=None: mock_resp
    mock_resp.__exit__ = lambda *a: None

    with patch.object(ph, "urlopen", return_value=mock_resp):
        assert ph._prom_query("sum(up)") == 12.25


def test_prom_query_empty_result_zero() -> None:
    sample = {"status": "success", "data": {"resultType": "vector", "result": []}}
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(sample).encode("utf-8")
    mock_resp.__enter__ = lambda self=None: mock_resp
    mock_resp.__exit__ = lambda *a: None

    with patch.object(ph, "urlopen", return_value=mock_resp):
        assert ph._prom_query("sum(up)") == 0.0


def test_max_ts_column_for_table_resolves_known_columns() -> None:
    """Resuelve la primera columna de tiempo presente (orden fijo en el helper)."""
    result = MagicMock()
    result.fetchall.return_value = [("id",), ("side",), ("created_at",)]
    mock_session = MagicMock()
    mock_session.execute.return_value = result
    # Sin 'timestamp' en el esquema, usa 'created_at'
    assert ph._max_ts_column_for_table(mock_session, "trades") == "created_at"
    result.fetchall.return_value = [("id",), ("timestamp",)]
    assert ph._max_ts_column_for_table(mock_session, "trades") == "timestamp"


def test_write_reports_creates_latest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ph, "REPORTS_DIR", tmp_path)
    payload = {"ok": True, "checks": {}}
    path = ph._write_reports(payload)
    assert path.exists()
    latest = tmp_path / "pipeline_health" / "LATEST.json"
    assert latest.exists()
    assert json.loads(latest.read_text(encoding="utf-8"))["ok"] is True
