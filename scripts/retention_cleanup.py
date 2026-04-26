#!/usr/bin/env python3
"""
Retención y compresión de artefactos de monitoreo y reportes

Políticas:
- MONITORING_DIR
  - monitoring_summary_*: retener 90 días; comprimir >30 días a .gz
  - continuous_72h_monitoring_data_*: retener 30 días (borrar >30)
  - intensive_monitoring_report_* y extended_monitoring_report_*: retener 90 días

- REPORTS_DIR
  - audits/, incidents/, safety/: retener 365 días
  - stabilization/, performance/, integrity/: retener 180 días
  - phase8/, plans/: retener 365 días

- tests/reports/: retener 14 días

Uso:
  MONITORING_DIR=monitoring_data REPORTS_DIR=reports python scripts/retention_cleanup.py [--dry-run] [--verbose]
"""

from __future__ import annotations

import os
import sys
import gzip
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Tuple


@dataclass
class Policy:
    glob_patterns: Tuple[str, ...]
    retain_days: int
    compress_after_days: int | None = None  # solo para summaries


def parse_ts_from_name(path: Path) -> datetime | None:
    name = path.name
    # Try common suffixes: _YYYYMMDD_HHMMSS or _YYYYMMDD
    try:
        if ".json" in name:
            stem = name[:-5]
        elif name.endswith(".json.gz"):
            stem = name[:-8]
        else:
            stem = name
        parts = stem.split("_")
        for i in range(len(parts) - 1, -1, -1):
            token = parts[i]
            if (
                len(token) == 15 and token.isdigit()
            ):  # YYYYMMDD_HHMMSS without underscore
                return datetime.strptime(token, "%Y%m%d%H%M%S").replace(
                    tzinfo=timezone.utc
                )
            if len(token) == 8 and token.isdigit():  # YYYYMMDD
                return datetime.strptime(token, "%Y%m%d").replace(tzinfo=timezone.utc)
            if (
                i >= 1
                and len(parts[i - 1]) == 8
                and parts[i - 1].isdigit()
                and len(parts[i]) == 6
                and parts[i].isdigit()
            ):
                return datetime.strptime(
                    parts[i - 1] + parts[i], "%Y%m%d%H%M%S"
                ).replace(tzinfo=timezone.utc)
    except Exception:
        return None
    return None


def file_age_days(path: Path, now: datetime) -> float:
    ts = parse_ts_from_name(path)
    if ts is None:
        # fallback to mtime
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        ts = mtime
    return (now - ts).total_seconds() / 86400.0


def gzip_json_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as f_in, gzip.open(target, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)


def apply_policies(
    base_dir: Path,
    policies: Iterable[Policy],
    now: datetime,
    dry_run: bool,
    verbose: bool,
) -> Tuple[int, int]:
    deleted = 0
    compressed = 0

    for policy in policies:
        for pattern in policy.glob_patterns:
            for path in base_dir.glob(pattern):
                if not path.is_file():
                    continue
                age = file_age_days(path, now)

                # Compress if applicable
                if policy.compress_after_days is not None and path.suffix == ".json":
                    if age > policy.compress_after_days and age <= policy.retain_days:
                        gz_path = path.with_suffix(path.suffix + ".gz")
                        if not gz_path.exists():
                            if verbose:
                                print(
                                    f"[COMPRESS] {path} -> {gz_path} (age {age:.1f}d)"
                                )
                            if not dry_run:
                                try:
                                    gzip_json_file(path, gz_path)
                                    compressed += 1
                                except Exception as e:
                                    print(f"[WARN] No se pudo comprimir {path}: {e}")

                # Delete beyond retention (delete both .json and .json.gz)
                if age > policy.retain_days:
                    # if we are on .json.gz try delete; also handle .json counterpart
                    targets = [path]
                    if path.suffix == ".json":
                        gz = path.with_suffix(path.suffix + ".gz")
                        if gz.exists():
                            targets.append(gz)
                    elif path.suffixes[-2:] == [".json", ".gz"]:
                        json_path = path.with_suffix("")  # remove .gz
                        if json_path.exists():
                            targets.append(json_path)

                    for t in set(targets):
                        if verbose:
                            print(
                                f"[DELETE] {t} (age {age:.1f}d > {policy.retain_days}d)"
                            )
                        if not dry_run:
                            try:
                                t.unlink(missing_ok=True)
                                deleted += 1
                            except Exception as e:
                                print(f"[WARN] No se pudo borrar {t}: {e}")

    return deleted, compressed


def main(argv: list[str]) -> int:
    dry_run = "--dry-run" in argv or "-n" in argv
    verbose = "--verbose" in argv or "-v" in argv

    monitoring_dir = Path(os.getenv("MONITORING_DIR", "monitoring_data"))
    reports_dir = Path(os.getenv("REPORTS_DIR", "reports"))
    tests_reports_dir = Path("tests/reports")

    now = datetime.now(tz=timezone.utc)

    # Policies
    monitoring_policies = [
        Policy(
            ("monitoring_summary_*.json", "monitoring_summary_*.json.gz"),
            retain_days=90,
            compress_after_days=30,
        ),
        Policy(
            (
                "continuous_72h_monitoring_data_*.json",
                "continuous_72h_monitoring_data_*.json.gz",
            ),
            retain_days=30,
        ),
        Policy(
            (
                "intensive_monitoring_report_*.json",
                "intensive_monitoring_report_*.json.gz",
            ),
            retain_days=90,
        ),
        Policy(
            (
                "extended_monitoring_report_*.json",
                "extended_monitoring_report_*.json.gz",
            ),
            retain_days=90,
        ),
    ]

    reports_policies = [
        # 365 days
        Policy(("audits/*.json", "audits/*.json.gz"), retain_days=365),
        Policy(("incidents/*.json", "incidents/*.json.gz"), retain_days=365),
        Policy(("safety/*.json", "safety/*.json.gz"), retain_days=365),
        Policy(("phase8/*.json", "phase8/*.json.gz"), retain_days=365),
        Policy(("plans/*.json", "plans/*.json.gz"), retain_days=365),
        # 180 days
        Policy(("stabilization/*.json", "stabilization/*.json.gz"), retain_days=180),
        Policy(("performance/*.json", "performance/*.json.gz"), retain_days=180),
        Policy(("integrity/*.json", "integrity/*.json.gz"), retain_days=180),
    ]

    tests_policies = [
        Policy(("*.json", "*.json.gz"), retain_days=14),
    ]

    total_deleted = 0
    total_compressed = 0

    if monitoring_dir.exists():
        d, c = apply_policies(
            monitoring_dir, monitoring_policies, now, dry_run, verbose
        )
        total_deleted += d
        total_compressed += c
    else:
        if verbose:
            print(f"[INFO] MONITORING_DIR no existe: {monitoring_dir}")

    if reports_dir.exists():
        d, c = apply_policies(reports_dir, reports_policies, now, dry_run, verbose)
        total_deleted += d
        total_compressed += c
    else:
        if verbose:
            print(f"[INFO] REPORTS_DIR no existe: {reports_dir}")

    if tests_reports_dir.exists():
        d, c = apply_policies(tests_reports_dir, tests_policies, now, dry_run, verbose)
        total_deleted += d
        total_compressed += c

    print(
        f"Resumen: comprimidos={total_compressed}, eliminados={total_deleted}, dry_run={dry_run}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
