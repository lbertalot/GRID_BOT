"""
Watchdog de ingesta API → DB: verifica escrituras recientes cada ~15 min.

- Preferencia: PromQL `increase(db_writes_total{...}[65m])` vía Prometheus HTTP API.
- Fallback si Prometheus no responde: timestamps máximos en PostgreSQL.
- Evidencia: JSON en REPORTS_DIR/pipeline_health/ (LATEST + timestamp).
- Fallo duro (excepción Celery) si una tabla crítica incumple el umbral.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from celery import shared_task
from sqlalchemy import text

from app.db.session import SessionLocal

logger = logging.getLogger(__name__)

PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://127.0.0.1:9090").rstrip("/")
REPORTS_DIR = Path(os.getenv("REPORTS_DIR", "reports")).resolve()
WINDOW = "65m"
# Snapshots Celery cada 15m: margen 2× + buffer
SNAPSHOT_MAX_AGE_MIN = int(os.getenv("PIPELINE_HEALTH_SNAPSHOT_MAX_AGE_MIN", "35"))
# alerts puede estar quieto en horas sin eventos: solo advertencia, no falla la tarea
ALERTS_SOFT_ONLY = os.getenv("PIPELINE_HEALTH_ALERTS_SOFT", "true").lower() in ("1", "true", "yes")


def _prom_query(query: str, timeout_s: float = 10.0) -> Optional[float]:
    """Ejecuta instant query; devuelve el valor escalar o None si falla."""
    params = urlencode({"query": query})
    url = f"{PROMETHEUS_URL}/api/v1/query?{params}"
    try:
        req = Request(url, headers={"Accept": "application/json"})
        with urlopen(req, timeout=timeout_s) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except (URLError, OSError, json.JSONDecodeError, ValueError) as exc:
        logger.warning("[PipelineHealth] Prometheus no disponible (%s): %s", url, exc)
        return None

    if body.get("status") != "success":
        logger.warning("[PipelineHealth] Prometheus respuesta no success: %s", body.get("status"))
        return None

    data = body.get("data") or {}
    results = data.get("result") or []
    if not results:
        return 0.0
    try:
        return float(results[0]["value"][1])
    except (KeyError, IndexError, TypeError, ValueError):
        return 0.0


def _db_scalar(session, sql: str, params: Optional[Dict[str, Any]] = None) -> Any:
    row = session.execute(text(sql), params or {}).fetchone()
    return row[0] if row else None


def _max_ts_column_for_table(session, table: str) -> str:
    """
    Columna de tiempo a usar en MAX() para comprobar actividad reciente.
    Alinea con esquemas que usan timestamp, created_at, etc.
    """
    q = text(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = :t
        """
    )
    names = {r[0] for r in session.execute(q, {"t": table}).fetchall()}
    for cand in ("timestamp", "created_at", "updated_at", "executed_at", "captured_at"):
        if cand in names:
            return cand
    return "timestamp"


def _write_reports(payload: Dict[str, Any]) -> Path:
    out = REPORTS_DIR / "pipeline_health"
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path_ts = out / f"health_{stamp}.json"
    path_ts.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    (out / "LATEST.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    daily = out / f"daily_{day}.jsonl"
    with daily.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, default=str) + "\n")

    return path_ts


def _check_table_prometheus(table: str) -> Optional[float]:
    """sum(increase(db_writes_total{table,status=ok}[WINDOW])) o None si Prom no responde."""
    q = f'sum(increase(db_writes_total{{table="{table}",status="ok"}}[{WINDOW}]))'
    return _prom_query(q)


def _sql_fallback_checks(session) -> Dict[str, Any]:
    """Cuando Prometheus no está: heurística por MAX(timestamp) en tablas."""
    out: Dict[str, Any] = {}
    now = datetime.now(timezone.utc)
    cutoff_snap = now - timedelta(minutes=SNAPSHOT_MAX_AGE_MIN)
    cutoff_row = now - timedelta(minutes=65)

    max_cap = _db_scalar(
        session,
        "SELECT MAX(captured_at) FROM portfolio_snapshots",
    )
    snap_ok = max_cap is not None and max_cap >= cutoff_snap
    out["portfolio_snapshots"] = {
        "source": "sql",
        "max_captured_at": str(max_cap) if max_cap else None,
        "ok": bool(snap_ok),
    }

    for table, default_col in (
        ("balances", "updated_at"),
        ("trades", "timestamp"),
        ("performance_metrics", "timestamp"),
    ):
        col = default_col
        if table in ("trades", "performance_metrics"):
            col = _max_ts_column_for_table(session, table)
        elif table == "balances":
            bcols = {r[0] for r in session.execute(
                text(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'balances'
                    """
                )
            ).fetchall()}
            col = "updated_at" if "updated_at" in bcols else default_col
        mx = _db_scalar(session, f"SELECT MAX({col}) FROM {table}")
        row_ok = mx is not None and mx >= cutoff_row
        out[table] = {
            "source": "sql",
            f"max_{col}": str(mx) if mx else None,
            "ok": bool(row_ok),
        }

    max_al = _db_scalar(session, "SELECT MAX(created_at) FROM alerts")
    # Sin alertas recientes no es fallo duro
    out["alerts"] = {
        "source": "sql",
        "max_created_at": str(max_al) if max_al else None,
        "ok": True,
        "note": "alerts_soft_in_sql_fallback",
    }
    return out


@shared_task(
    name="app.services.pipeline_health_tasks.check_pipeline_db_writes",
    bind=True,
    max_retries=0,
)
def check_pipeline_db_writes(self) -> Dict[str, Any]:
    """
    Comprueba que haya escrituras `db_writes_total` en ~65m por tabla crítica
    y que `portfolio_snapshots` tenga captura reciente (SQL).

    Lanza RuntimeError si falla algún check duro.
    """
    started = datetime.now(timezone.utc)
    tables_prom = ("trades", "balances", "performance_metrics", "alerts")
    checks: Dict[str, Any] = {}
    failures: List[str] = []
    prom_responded = False

    for tbl in tables_prom:
        parsed = _check_table_prometheus(tbl)
        if parsed is not None:
            prom_responded = True
        ok = parsed is not None and parsed > 0
        checks[tbl] = {"source": "prometheus", "increase_sum": parsed, "ok": ok}
        if tbl == "alerts" and ALERTS_SOFT_ONLY:
            checks[tbl]["severity"] = "warning"
            if not ok:
                checks[tbl]["warning"] = "sin escrituras alerts en ventana (no bloquea)"
        elif not ok and not (tbl == "alerts" and ALERTS_SOFT_ONLY):
            if parsed is None:
                failures.append(f"{tbl}: Prometheus sin datos para increase en [{WINDOW}]")
            else:
                failures.append(
                    f"{tbl}: increase(db_writes_total status=ok) en [{WINDOW}] == 0"
                )

    # portfolio_snapshots: sin contador de métricas dedicado → SQL siempre
    db = SessionLocal()
    try:
        max_cap = _db_scalar(
            db,
            "SELECT MAX(captured_at) FROM portfolio_snapshots",
        )
        cutoff = started - timedelta(minutes=SNAPSHOT_MAX_AGE_MIN)
        snap_ok = max_cap is not None and max_cap >= cutoff
        checks["portfolio_snapshots"] = {
            "source": "sql",
            "max_captured_at": str(max_cap) if max_cap else None,
            "ok": bool(snap_ok),
        }
        if not snap_ok:
            failures.append(
                f"portfolio_snapshots: última captura antigua o vacía "
                f"(>{SNAPSHOT_MAX_AGE_MIN}m, max={max_cap})"
            )

        # Si Prometheus no respondió (ninguna query con valor), fallback SQL
        if not prom_responded:
            logger.warning("[PipelineHealth] Usando fallback SQL (Prometheus no consultable)")
            fb = _sql_fallback_checks(db)
            checks["_sql_fallback"] = fb
            failures = [f for f in failures if "Prometheus sin datos" not in f]
            for tbl in ("trades", "balances", "performance_metrics"):
                if tbl in fb:
                    checks[tbl]["sql_fallback"] = fb[tbl]
                    if fb[tbl].get("ok"):
                        checks[tbl]["ok"] = True
                    else:
                        checks[tbl]["ok"] = False
                        failures.append(
                            f"{tbl}: fallback SQL — sin actividad reciente "
                            f"(max timestamp > 65m o tabla vacía)"
                        )
    finally:
        db.close()

    hard_failures = list(failures)

    payload: Dict[str, Any] = {
        "checked_at_utc": started.isoformat(),
        "prometheus_url": PROMETHEUS_URL,
        "window": WINDOW,
        "checks": checks,
        "failures": hard_failures,
        "ok": len(hard_failures) == 0,
    }

    path = _write_reports(payload)

    # Métricas exportadas por el worker (mismo proceso que prometheus_client)
    try:
        from app.core.metrics import pipeline_health_table_ok

        for name, c in checks.items():
            if name.startswith("_"):
                continue
            if isinstance(c, dict) and "ok" in c:
                pipeline_health_table_ok.labels(table=name).set(1 if c["ok"] else 0)
    except Exception as exc:
        logger.debug("[PipelineHealth] No se pudo actualizar pipeline_health_table_ok: %s", exc)

    if hard_failures:
        msg = "; ".join(hard_failures)
        logger.error("[PipelineHealth] FALLO: %s (evidencia: %s)", msg, path)
        raise RuntimeError(f"pipeline_health: {msg}")

    logger.info("[PipelineHealth] OK — evidencia %s", path)
    return {"status": "ok", "report": str(path), "checked_at": payload["checked_at_utc"]}
