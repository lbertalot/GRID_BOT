#!/usr/bin/env python3
"""
Un ciclo: recolecta logs de Docker Compose y aplica heurísticas locales.

Integración con Antigravity: el informe Markdown/JSON alimenta el paso
"Análisis con skills" descrito en docs/OPS_WATCH_ANTIGRAVITY.md.

Uso:
  python3 scripts/ops_watch/run_once.py
  python3 scripts/ops_watch/run_once.py --config scripts/ops_watch/config.example.json

Códigos de salida:
  0 = salud green
  1 = yellow
  2 = red
  3 = error de ejecución (docker falló, config inválida, etc.)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from collector import collect_compose_logs
from heuristics import Health, analyze_log_text


def _repo_root() -> Path:
    """Raíz del repo (grid_bot): .../scripts/ops_watch/run_once.py -> parents[2]."""
    return Path(__file__).resolve().parents[2]


def _load_config(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _write_report(
    out_dir: Path,
    *,
    stamp: str,
    repo_root: Path,
    collect_cmd: list[str],
    truncated: bool,
    raw_path: Path,
    report_md: str,
    report_json: dict,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"report_{stamp}.json"
    md_path = out_dir / f"report_{stamp}.md"
    json_path.write_text(json.dumps(report_json, indent=2), encoding="utf-8")
    md_path.write_text(report_md, encoding="utf-8")
    (out_dir / "LATEST.md").write_text(report_md, encoding="utf-8")
    (out_dir / "LATEST.json").write_text(json.dumps(report_json, indent=2), encoding="utf-8")
    try:
        raw_rel = str(raw_path.relative_to(repo_root))
    except ValueError:
        raw_rel = str(raw_path)
    meta = {
        "timestamp_utc": stamp,
        "collect_command": collect_cmd,
        "truncated": truncated,
        "raw_log_path": str(raw_path),
        "raw_log_relative": raw_rel,
    }
    (out_dir / "LATEST.meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ops watch: un ciclo de logs + heurísticas.")
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="JSON de configuración (por defecto: scripts/ops_watch/config.json si existe, si no example).",
    )
    args = parser.parse_args(argv)

    root = _repo_root()
    cfg_path = args.config
    if cfg_path is None:
        preferred = root / "scripts" / "ops_watch" / "config.json"
        cfg_path = preferred if preferred.exists() else root / "scripts" / "ops_watch" / "config.example.json"

    try:
        cfg = _load_config(cfg_path)
    except (OSError, json.JSONDecodeError) as e:
        print(f"Config error ({cfg_path}): {e}", file=sys.stderr)
        return 3

    compose_file = str(cfg.get("compose_file", "docker-compose.local.yml"))
    since = str(cfg.get("since", "10m"))
    services = list(cfg.get("services", ["api", "worker", "beat"]))
    max_bytes = int(cfg.get("max_log_bytes", 5_242_880))
    timeout_sec = int(cfg.get("docker_timeout_sec", 120))
    out_rel = str(cfg.get("output_dir", "reports/ops_watch"))
    out_dir = root / out_rel

    try:
        collected = collect_compose_logs(
            root,
            compose_file=compose_file,
            services=services,
            since=since,
            max_bytes=max_bytes,
            timeout_sec=timeout_sec,
        )
    except subprocess.TimeoutExpired:
        print("docker compose logs: timeout", file=sys.stderr)
        return 3
    except FileNotFoundError:
        print("docker no encontrado en PATH", file=sys.stderr)
        return 3

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_path = out_dir / f"raw_{stamp}.log"
    raw_path.write_text(collected.text, encoding="utf-8")

    heur = analyze_log_text(collected.text)
    report_json = {
        "config_path": str(cfg_path),
        "compose_file": compose_file,
        "since": since,
        "services": services,
        "truncated": collected.truncated,
        "heuristics": heur.to_dict(),
    }

    lines = [
        f"# Ops watch — {stamp}",
        "",
        f"- **Salud heurística:** `{heur.health.value}`",
        f"- **Score:** {heur.score}",
        f"- **Ventana:** `--since={since}` · servicios: {', '.join(services)}",
        f"- **Truncado:** {'sí' if collected.truncated else 'no'}",
        "",
        "## Conteos",
        "",
    ]
    if heur.counts:
        for k, v in sorted(heur.counts.items()):
            lines.append(f"- `{k}`: {v}")
    else:
        lines.append("_Sin coincidencias de patrones._")
    lines.extend(["", "## Notas", ""])
    lines.extend(f"- {n}" for n in heur.notes) if heur.notes else lines.append("_Ninguna._")

    try:
        raw_rel = str(raw_path.relative_to(root))
    except ValueError:
        raw_rel = str(raw_path)
    try:
        out_rel = str(out_dir.relative_to(root))
    except ValueError:
        out_rel = str(out_dir)
    cmd_line = " ".join(collected.command)
    lines.extend(
        [
            "",
            "## Artefactos y metadatos",
            "",
            f"- **Log crudo:** `{raw_rel}`",
            f"- **Metadatos del ciclo:** `{out_rel}/LATEST.meta.json` (`collect_command`, `truncated`, `raw_log_path`, `raw_log_relative`)",
            f"- **Heurísticas (JSON):** `{out_rel}/LATEST.json`",
            f"- **Comando de recolección:** `{cmd_line}`",
            "",
            "## Siguiente paso (Antigravity)",
            "",
            "Abrir `docs/OPS_WATCH_ANTIGRAVITY.md` y ejecutar el workflow con los skills indicados,",
            "usando este `LATEST.md` y, para trazas largas o truncado, el `raw_*.log` indicado arriba (ver también `LATEST.meta.json`).",
            "",
        ]
    )
    report_md = "\n".join(lines)

    report_json["artifacts"] = {
        "stamp": stamp,
        "raw_log_relative": raw_rel,
        "meta_relative": f"{out_rel}/LATEST.meta.json",
    }

    _write_report(
        out_dir,
        stamp=stamp,
        repo_root=root,
        collect_cmd=collected.command,
        truncated=collected.truncated,
        raw_path=raw_path,
        report_md=report_md,
        report_json=report_json,
    )

    print(report_md)
    if heur.health == Health.RED:
        return 2
    if heur.health == Health.YELLOW:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
