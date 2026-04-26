#!/usr/bin/env python3
"""
Auditor E2E del pipeline de datos:
API externa -> transformación -> persistencia PostgreSQL.

Genera evidencia verificable en reports/ops_watch/:
- data_pipeline_audit_<timestamp>.md
- data_pipeline_audit_<timestamp>.json
- DATA_PIPELINE_AUDIT_LATEST.md/json
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "reports" / "ops_watch"


@dataclass
class CmdResult:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str


def run_cmd(command: list[str], cwd: Path | None = None) -> CmdResult:
    proc = subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        check=False,
    )
    return CmdResult(command=command, returncode=proc.returncode, stdout=proc.stdout, stderr=proc.stderr)


def psql(query: str) -> CmdResult:
    return run_cmd(
        [
            "docker",
            "exec",
            "gridbot_db",
            "psql",
            "-U",
            "gridbot",
            "-d",
            "gridbot",
            "-t",
            "-A",
            "-F",
            "|",
            "-c",
            query,
        ]
    )


def parse_pipe_table(stdout: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append([p.strip() for p in line.split("|")])
    return rows


def main() -> int:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Fase rápida: salud runtime + auth patterns
    ps = run_cmd(["docker", "compose", "-f", "docker-compose.local.yml", "ps"], cwd=ROOT)
    logs = run_cmd(
        [
            "docker",
            "compose",
            "-f",
            "docker-compose.local.yml",
            "logs",
            "--since=30m",
            "api",
            "worker",
            "beat",
            "--no-color",
            "--timestamps",
        ],
        cwd=ROOT,
    )
    log_text = logs.stdout
    auth_2015 = len(re.findall(r"code=-2015|Invalid API-key, IP, or permissions", log_text, re.I))
    ws_auth_fail = len(re.findall(r"session\.logon fallido|WS API v3.*ERROR", log_text, re.I))
    execute_error = len(re.findall(r"execute_trading_cycle.*\{'status': 'error'", log_text, re.I))
    hold_decisions = len(re.findall(r"Strategy selected .*: HOLD", log_text, re.I))

    # Fase media: actividad en tablas y drift de esquema
    counts_q = """
    SELECT 'portfolio_snapshots', COUNT(*), COALESCE(MAX(captured_at)::text, '')
    FROM portfolio_snapshots
    UNION ALL
    SELECT 'trades', COUNT(*), COALESCE(MAX(executed_at)::text, '')
    FROM trades
    UNION ALL
    SELECT 'balances', COUNT(*), COALESCE(MAX(updated_at)::text, '')
    FROM balances
    UNION ALL
    SELECT 'alerts', COUNT(*), COALESCE(MAX(created_at)::text, '')
    FROM alerts
    ORDER BY 1;
    """
    counts_r = psql(counts_q)
    counts_rows = parse_pipe_table(counts_r.stdout)

    # Drift orientado a los modelos actualmente usados en código
    drift_checks = {
        "trades_missing_for_model": psql(
            """
            SELECT column_name FROM (
              VALUES ('entry_price'), ('exit_price'), ('profit_loss'), ('timestamp')
            ) AS expected(column_name)
            WHERE NOT EXISTS (
              SELECT 1 FROM information_schema.columns c
              WHERE c.table_schema='public' AND c.table_name='trades' AND c.column_name=expected.column_name
            )
            ORDER BY 1;
            """
        ),
        "balances_missing_for_model": psql(
            """
            SELECT column_name FROM (
              VALUES ('asset'), ('amount'), ('version')
            ) AS expected(column_name)
            WHERE NOT EXISTS (
              SELECT 1 FROM information_schema.columns c
              WHERE c.table_schema='public' AND c.table_name='balances' AND c.column_name=expected.column_name
            )
            ORDER BY 1;
            """
        ),
        "alerts_missing_for_model": psql(
            """
            SELECT column_name FROM (
              VALUES ('level'), ('sent_to_telegram')
            ) AS expected(column_name)
            WHERE NOT EXISTS (
              SELECT 1 FROM information_schema.columns c
              WHERE c.table_schema='public' AND c.table_name='alerts' AND c.column_name=expected.column_name
            )
            ORDER BY 1;
            """
        ),
    }
    drift_summary = {k: [r[0] for r in parse_pipe_table(v.stdout)] for k, v in drift_checks.items()}

    report: dict[str, Any] = {
        "timestamp_utc": stamp,
        "quick_phase": {
            "docker_compose_ps_rc": ps.returncode,
            "auth_2015_count_30m": auth_2015,
            "ws_auth_fail_count_30m": ws_auth_fail,
            "execute_trading_cycle_error_count_30m": execute_error,
            "hold_decision_count_30m": hold_decisions,
        },
        "medium_phase": {
            "table_activity": [
                {"table": r[0], "rows": int(r[1]), "last_event": r[2]} for r in counts_rows if len(r) >= 3
            ],
            "schema_drift": drift_summary,
        },
        "evidence": {
            "compose_ps_excerpt": ps.stdout.splitlines()[:20],
            "counts_query_rc": counts_r.returncode,
        },
    }

    # Fase robusta: hipótesis y validaciones sugeridas
    hypotheses: list[dict[str, Any]] = []
    if auth_2015 > 0:
        hypotheses.append(
            {
                "id": "H_AUTH_2015",
                "priority": "P1",
                "probability": "alta",
                "impact": "alto",
                "description": "Fallo de credenciales/permisos/IP Binance bloquea WS y ciclo de trading.",
            }
        )
    if any(drift_summary.values()):
        hypotheses.append(
            {
                "id": "H_SCHEMA_DRIFT",
                "priority": "P1",
                "probability": "alta",
                "impact": "alto",
                "description": "Desalineación entre modelos ORM y esquema real de tablas en PostgreSQL.",
            }
        )
    if hold_decisions > 0:
        hypotheses.append(
            {
                "id": "H_STRATEGY_HOLD",
                "priority": "P2",
                "probability": "media",
                "impact": "medio",
                "description": "La estrategia decide HOLD y reduce probabilidad de escrituras en trades.",
            }
        )
    report["robust_phase"] = {"prioritized_hypotheses": hypotheses}

    md_lines = [
        f"# Data Pipeline Audit — {stamp}",
        "",
        "## Resumen rápido",
        "",
        f"- auth `-2015` en 30m: **{auth_2015}**",
        f"- fallos WS auth en 30m: **{ws_auth_fail}**",
        f"- `execute_trading_cycle` con status error en 30m: **{execute_error}**",
        f"- decisiones HOLD en 30m: **{hold_decisions}**",
        "",
        "## Actividad de tablas",
        "",
    ]
    for row in report["medium_phase"]["table_activity"]:
        md_lines.append(f"- `{row['table']}`: rows={row['rows']}, last_event=`{row['last_event']}`")
    md_lines.extend(
        [
            "",
            "## Drift de esquema detectado",
            "",
            f"- `trades_missing_for_model`: {', '.join(drift_summary['trades_missing_for_model']) or 'ninguno'}",
            f"- `balances_missing_for_model`: {', '.join(drift_summary['balances_missing_for_model']) or 'ninguno'}",
            f"- `alerts_missing_for_model`: {', '.join(drift_summary['alerts_missing_for_model']) or 'ninguno'}",
            "",
            "## Hipótesis priorizadas",
            "",
        ]
    )
    if hypotheses:
        for h in hypotheses:
            md_lines.append(
                f"- `{h['id']}` ({h['priority']} · prob={h['probability']} · impacto={h['impact']}): {h['description']}"
            )
    else:
        md_lines.append("- Sin hipótesis críticas detectadas por este barrido.")

    md_text = "\n".join(md_lines) + "\n"

    json_path = OUT_DIR / f"data_pipeline_audit_{stamp}.json"
    md_path = OUT_DIR / f"data_pipeline_audit_{stamp}.md"
    latest_json = OUT_DIR / "DATA_PIPELINE_AUDIT_LATEST.json"
    latest_md = OUT_DIR / "DATA_PIPELINE_AUDIT_LATEST.md"

    json_text = json.dumps(report, indent=2, ensure_ascii=True)
    json_path.write_text(json_text, encoding="utf-8")
    md_path.write_text(md_text, encoding="utf-8")
    latest_json.write_text(json_text, encoding="utf-8")
    latest_md.write_text(md_text, encoding="utf-8")

    print(md_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

