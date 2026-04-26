"""Heurísticas locales sobre texto de logs (sin LLM). Extensible."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Final


class Health(str, Enum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


@dataclass(frozen=True)
class Signal:
    name: str
    pattern: re.Pattern[str]
    weight: int


_SIGNALS: Final[tuple[Signal, ...]] = (
    Signal("traceback", re.compile(r"Traceback \(most recent call last\)", re.I), 3),
    Signal("exception", re.compile(r"\bERROR\b|\bCRITICAL\b|Exception:|Error:", re.I), 2),
    Signal("db_unreachable", re.compile(r"connection refused.*5432|could not connect|OperationalError", re.I), 3),
    Signal("redis_unreachable", re.compile(r"redis.*connection|ConnectionError.*6379", re.I), 3),
    Signal("celery_chord", re.compile(r"celery.*(error|failed|retry)", re.I), 1),
    # Evita falsos positivos por timestamps (.429...) y busca contexto HTTP real.
    Signal(
        "rate_limit",
        re.compile(
            r"Too Many Requests|(?:HTTP(?:/\d(?:\.\d)?)?|status|code)\s*[:=]?\s*429\b",
            re.I,
        ),
        1,
    ),
)


@dataclass
class HeuristicReport:
    counts: dict[str, int] = field(default_factory=dict)
    score: int = 0
    health: Health = Health.GREEN
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "counts": dict(self.counts),
            "score": self.score,
            "health": self.health.value,
            "notes": list(self.notes),
        }


def analyze_log_text(text: str, *, yellow_threshold: int = 8, red_threshold: int = 20) -> HeuristicReport:
    """Cuenta señales y asigna un score burdo. Umbrales ajustables."""
    report = HeuristicReport()
    if not text.strip():
        report.notes.append("Sin líneas de log en la ventana solicitada.")
        return report

    for sig in _SIGNALS:
        n = len(sig.pattern.findall(text))
        if n:
            report.counts[sig.name] = n
            report.score += n * sig.weight

    if report.score >= red_threshold:
        report.health = Health.RED
        report.notes.append(f"Score {report.score} >= red_threshold {red_threshold}")
    elif report.score >= yellow_threshold:
        report.health = Health.YELLOW
        report.notes.append(f"Score {report.score} >= yellow_threshold {yellow_threshold}")

    return report
