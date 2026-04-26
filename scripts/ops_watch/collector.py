"""Recolección de logs vía Docker Compose (subprocess)."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CollectResult:
    text: str
    truncated: bool
    command: list[str]


def collect_compose_logs(
    repo_root: Path,
    *,
    compose_file: str,
    services: list[str],
    since: str,
    max_bytes: int,
    timeout_sec: int,
) -> CollectResult:
    cmd = [
        "docker",
        "compose",
        "-f",
        compose_file,
        "logs",
        "--no-color",
        "--timestamps",
        f"--since={since}",
        *services,
    ]
    proc = subprocess.run(
        cmd,
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=timeout_sec,
        check=False,
    )
    raw = proc.stdout or ""
    if proc.stderr:
        raw += "\n# stderr from docker compose:\n" + proc.stderr

    truncated = False
    if len(raw.encode("utf-8")) > max_bytes:
        raw = raw[-max_bytes:]
        truncated = True

    return CollectResult(text=raw, truncated=truncated, command=cmd)
