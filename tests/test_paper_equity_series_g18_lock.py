"""G18/G19 — lock Redis TTL 5s + reload bajo lock (carrera prefork).

RCA: Docs/ops/research/RCA-G18-G19-series.md
Paper-only. PROMOTE_LIVE: NO. Prohibido file-lock.
"""

from __future__ import annotations

import json
import multiprocessing
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from decimal import Decimal

from app.core.distributed_lock import reset_redis_client
from app.core.paper_equity_ledger import (
    SERIES_LOCK_KEY,
    SERIES_LOCK_TTL_SECONDS,
    PaperEquitySeries,
    PaperLedgerError,
    reset_paper_telemetry,
)

G18_GAP_SECONDS = 2 * 3600
LOAD_WRITES = 1000
LOAD_PROCESSES = 2
LOAD_MAX_SECONDS = 30
D = Decimal


def _require_redis() -> str:
    reset_redis_client()
    try:
        from app.core.distributed_lock import get_redis_client

        client = get_redis_client()
        client.ping()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Redis no disponible para lock de serie: {exc}")
    url = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    return url


def _record_batch(payload: dict) -> dict:
    """Worker prefork: singleton propio + mismo JSON (spawn-safe)."""
    os.environ["PAPER_EQUITY_SERIES_LOCK"] = payload["lock"]
    os.environ["CB_SHARED_STORE"] = "memory"
    os.environ["REDIS_URL"] = payload["redis_url"]
    reset_redis_client()
    reset_paper_telemetry()
    path = Path(payload["path"])
    series = PaperEquitySeries(config_hash="g18g19", storage_path=path)
    base = datetime.fromisoformat(payload["base"])
    holds: list[float] = []
    for i in range(payload["count"]):
        t0 = time.perf_counter()
        series.record(
            D("1000.00"),
            at=base + timedelta(seconds=payload["start"] + i),
            deployed_capital=D("200"),
            config_hash="g18g19",
        )
        holds.append(time.perf_counter() - t0)
    holds.sort()
    p95 = holds[int(0.95 * (len(holds) - 1))] if holds else 0.0
    return {"count": payload["count"], "p95_s": p95}


def _run_two_process_load(*, series_path: Path, redis_url: str, lock: str) -> tuple[float, list[dict]]:
    base = datetime(2026, 9, 13, 12, 0, 0, tzinfo=timezone.utc)
    per = LOAD_WRITES // LOAD_PROCESSES
    ctx = multiprocessing.get_context("spawn")
    payloads = [
        {
            "path": str(series_path),
            "redis_url": redis_url,
            "lock": lock,
            "base": base.isoformat(),
            "start": 0,
            "count": per,
        },
        {
            "path": str(series_path),
            "redis_url": redis_url,
            "lock": lock,
            "base": base.isoformat(),
            "start": per,
            "count": LOAD_WRITES - per,
        },
    ]
    t0 = time.perf_counter()
    with ctx.Pool(LOAD_PROCESSES) as pool:
        pool.map(_record_batch, payloads)
    elapsed = time.perf_counter() - t0
    payload = json.loads(series_path.read_text(encoding="utf-8"))
    return elapsed, payload.get("samples") or []


def test_series_lock_ttl_is_five_seconds():
    assert SERIES_LOCK_TTL_SECONDS == 5
    assert SERIES_LOCK_KEY == "lock:paper:equity_series"


def test_record_fail_closed_si_redis_caido(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPER_EQUITY_SERIES_LOCK", "1")
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:1/0")
    reset_redis_client()
    reset_paper_telemetry()
    path = tmp_path / "paper_equity_series.json"
    series = PaperEquitySeries(config_hash="g18g19", storage_path=path)
    with pytest.raises(PaperLedgerError, match="series lock"):
        series.record(D("1000"), at=datetime(2026, 9, 13, tzinfo=timezone.utc))
    assert not path.exists()


def test_carga_1000_writes_dos_procesos_cero_gaps_g18(tmp_path, monkeypatch):
    """Stress prefork: 1000 record() / ≥2 procesos / <30s / 0 gaps >2h."""
    redis_url = _require_redis()
    monkeypatch.setenv("PAPER_EQUITY_SERIES_LOCK", "1")
    monkeypatch.setenv("REDIS_URL", redis_url)
    reset_redis_client()
    reset_paper_telemetry()
    series_path = tmp_path / "paper_equity_series.json"
    elapsed, samples = _run_two_process_load(
        series_path=series_path, redis_url=redis_url, lock="1"
    )
    assert elapsed < LOAD_MAX_SECONDS, f"carga tardó {elapsed:.2f}s (max {LOAD_MAX_SECONDS})"
    assert len(samples) == LOAD_WRITES, (
        f"last-writer-wins: {len(samples)} samples (esperado {LOAD_WRITES})"
    )
    instants = sorted(datetime.fromisoformat(s["at"]) for s in samples)
    max_gap = 0.0
    for prev, cur in zip(instants, instants[1:]):
        max_gap = max(max_gap, (cur - prev).total_seconds())
    assert max_gap < G18_GAP_SECONDS, f"gap clase G18/G19: {max_gap}s"
