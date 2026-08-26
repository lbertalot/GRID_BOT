"""Sidecar de contadores pipeline worker → API scrape.

Prometheus solo scrapea ``api:8000/metrics``. Los Counters incrementados en el
worker Celery viven en otro proceso. Patrón E3: persistir totales en volumen
compartido y aplicar delta con ``inc()`` al scrapear (igual que gauges LATEST).

Paper-only. Fail-soft — nunca rompe ingest ni /metrics.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_LOCK = threading.Lock()
_APPLIED: dict[str, float] = {}
_SIDECAR_NAME = "pipeline_metrics/COUNTERS.json"


def _reports_dir() -> Path:
    return Path(os.getenv("REPORTS_DIR", "reports"))


def _sidecar_path() -> Path:
    return _reports_dir() / _SIDECAR_NAME


def _labels_key(metric: str, labels: dict[str, str]) -> str:
    parts = [metric] + [f"{k}={v}" for k, v in sorted(labels.items())]
    return "|".join(parts)


def _parse_key(key: str) -> tuple[str, dict[str, str]]:
    parts = key.split("|")
    metric = parts[0]
    labels: dict[str, str] = {}
    for part in parts[1:]:
        if "=" in part:
            k, v = part.split("=", 1)
            labels[k] = v
    return metric, labels


def _load_unlocked() -> dict[str, Any]:
    path = _sidecar_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("counters"), dict):
            return data
    except FileNotFoundError:
        pass
    except Exception as exc:  # noqa: BLE001
        logger.debug("pipeline_metrics_sidecar: read failed: %s", exc)
    return {"counters": {}}


def _save_unlocked(data: dict[str, Any]) -> None:
    path = _sidecar_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, sort_keys=True), encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        logger.debug("pipeline_metrics_sidecar: write failed: %s", exc)


def bump_labeled_counter(metric: str, delta: float = 1.0, **labels: str) -> None:
    """Incrementa contador en sidecar (worker o API)."""
    if not labels:
        labels = {}
    key = _labels_key(metric, labels)
    with _LOCK:
        data = _load_unlocked()
        counters = data.setdefault("counters", {})
        counters[key] = float(counters.get(key, 0)) + float(delta)
        _save_unlocked(data)


def record_items_processed(stage: str) -> None:
    bump_labeled_counter("pipeline_events_processed_total", stage=stage)
    bump_labeled_counter("gridbot_items_processed_total", stage=stage)


def record_items_dropped(stage: str, reason: str) -> None:
    bump_labeled_counter(
        "pipeline_events_dropped_total", stage=stage, reason=reason
    )
    bump_labeled_counter("gridbot_items_dropped_total", stage=stage, reason=reason)


def record_pipeline_error(stage: str, error_type: str) -> None:
    bump_labeled_counter(
        "pipeline_errors_total", stage=stage, error_type=error_type
    )
    bump_labeled_counter("gridbot_pipeline_errors_total", error_type=error_type)


def record_db_write(*, table: str, operation: str, status: str) -> None:
    bump_labeled_counter(
        "db_writes_total", table=table, operation=operation, status=status
    )


def record_api_request(*, endpoint: str, status: str) -> None:
    bump_labeled_counter(
        "pipeline_api_requests_total", endpoint=endpoint, status=status
    )


def _inc_registered_counter(name: str, labels: dict[str, str], delta: float) -> None:
    from app.core import metrics as m

    registry: dict[str, Any] = {
        "pipeline_events_processed_total": m.pipeline_events_processed_total,
        "pipeline_events_dropped_total": m.pipeline_events_dropped_total,
        "pipeline_errors_total": m.pipeline_errors_total,
        "pipeline_api_requests_total": m.pipeline_api_requests_total,
        "db_writes_total": m.db_writes_total,
        "gridbot_items_processed_total": m.gridbot_items_processed_total,
        "gridbot_items_dropped_total": m.gridbot_items_dropped_total,
        "gridbot_pipeline_errors_total": m.gridbot_pipeline_errors_total,
    }
    counter = registry.get(name)
    if counter is None:
        return
    try:
        counter.labels(**labels).inc(delta)
    except Exception as exc:  # noqa: BLE001
        logger.debug("pipeline_metrics_sidecar: inc %s failed: %s", name, exc)


def hydrate_pipeline_counters() -> None:
    """Aplica delta del sidecar a counters del proceso API (llamar en /metrics)."""
    with _LOCK:
        data = _load_unlocked()
        counters = data.get("counters") or {}
        for key, total in counters.items():
            try:
                target = float(total)
            except (TypeError, ValueError):
                continue
            prev = _APPLIED.get(key, 0.0)
            delta = target - prev
            if delta <= 0:
                continue
            name, labels = _parse_key(key)
            _inc_registered_counter(name, labels, delta)
            _APPLIED[key] = target


__all__ = [
    "bump_labeled_counter",
    "record_items_processed",
    "record_items_dropped",
    "record_pipeline_error",
    "record_db_write",
    "record_api_request",
    "hydrate_pipeline_counters",
]
