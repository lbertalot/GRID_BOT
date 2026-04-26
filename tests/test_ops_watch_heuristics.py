"""Tests para heurísticas de ops_watch (sin Docker)."""

from __future__ import annotations

import sys
from pathlib import Path

OPS = Path(__file__).resolve().parents[1] / "scripts" / "ops_watch"
sys.path.insert(0, str(OPS))

from heuristics import Health, analyze_log_text  # noqa: E402


def test_empty_logs_green():
    r = analyze_log_text("")
    assert r.health == Health.GREEN
    assert r.score == 0


def test_traceback_red_by_score():
    body = "Traceback (most recent call last):\n" * 10
    r = analyze_log_text(body, red_threshold=5)
    assert r.health == Health.RED
    assert r.counts.get("traceback", 0) == 10


def test_mild_errors_yellow():
    text = "ERROR: something\nWARNING: x\n"
    r = analyze_log_text(text, yellow_threshold=1, red_threshold=100)
    assert r.health == Health.YELLOW


def test_rate_limit_does_not_match_timestamp_digits():
    text = "2026-04-20T12:22:08.4226429Z INFO keepalive\n"
    r = analyze_log_text(text)
    assert r.counts.get("rate_limit", 0) == 0


def test_rate_limit_does_not_match_fractional_second_429():
    text = "2026-04-20T12:24:22.429623527Z INFO keepalive\n"
    r = analyze_log_text(text)
    assert r.counts.get("rate_limit", 0) == 0


def test_rate_limit_matches_real_429():
    text = "HTTP 429 Too Many Requests\nstatus=429\ncode:429\n"
    r = analyze_log_text(text)
    assert r.counts.get("rate_limit", 0) >= 3
