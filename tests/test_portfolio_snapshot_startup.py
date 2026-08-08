"""TDD: capture-on-startup paper-safe (anti PaperSnapshotStale20m)."""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


@pytest.fixture
def paper_env(monkeypatch):
    monkeypatch.setenv("PAPER_TRADING", "true")
    monkeypatch.setenv("FORCE_REAL_MODE", "")
    monkeypatch.delenv("PORTFOLIO_SNAPSHOT_ON_STARTUP", raising=False)


def test_should_enqueue_true_in_paper(paper_env, monkeypatch):
    monkeypatch.setattr(
        "app.services.portfolio_snapshot_service.paper_equity_is_source_of_truth",
        lambda: True,
    )
    from app.services.portfolio_snapshot_service import (
        should_enqueue_startup_portfolio_snapshot,
    )

    assert should_enqueue_startup_portfolio_snapshot() is True


def test_should_enqueue_false_when_not_paper(monkeypatch):
    monkeypatch.setenv("PAPER_TRADING", "false")
    monkeypatch.setattr(
        "app.services.portfolio_snapshot_service.paper_equity_is_source_of_truth",
        lambda: False,
    )
    from app.services.portfolio_snapshot_service import (
        should_enqueue_startup_portfolio_snapshot,
    )

    assert should_enqueue_startup_portfolio_snapshot() is False


def test_should_enqueue_kill_switch(paper_env, monkeypatch):
    monkeypatch.setenv("PORTFOLIO_SNAPSHOT_ON_STARTUP", "false")
    monkeypatch.setattr(
        "app.services.portfolio_snapshot_service.paper_equity_is_source_of_truth",
        lambda: True,
    )
    from app.services.portfolio_snapshot_service import (
        should_enqueue_startup_portfolio_snapshot,
    )

    assert should_enqueue_startup_portfolio_snapshot() is False


def test_enqueue_calls_delay_when_paper(paper_env, monkeypatch):
    monkeypatch.setattr(
        "app.services.portfolio_snapshot_service.paper_equity_is_source_of_truth",
        lambda: True,
    )
    from app.services import portfolio_snapshot_service as pss

    mock_delay = MagicMock()
    monkeypatch.setattr(pss.capture_portfolio_snapshot, "delay", mock_delay)
    redis_client = MagicMock()
    redis_client.set.return_value = True
    monkeypatch.setattr("redis.Redis.from_url", lambda *_a, **_k: redis_client)
    assert pss.enqueue_startup_portfolio_snapshot() is True
    mock_delay.assert_called_once_with()


def test_enqueue_skips_delay_when_not_paper(monkeypatch):
    monkeypatch.setattr(
        "app.services.portfolio_snapshot_service.paper_equity_is_source_of_truth",
        lambda: False,
    )
    from app.services import portfolio_snapshot_service as pss

    mock_delay = MagicMock()
    monkeypatch.setattr(pss.capture_portfolio_snapshot, "delay", mock_delay)
    assert pss.enqueue_startup_portfolio_snapshot() is False
    mock_delay.assert_not_called()


def test_enqueue_debounce_skips_second_call(paper_env, monkeypatch):
    monkeypatch.setattr(
        "app.services.portfolio_snapshot_service.paper_equity_is_source_of_truth",
        lambda: True,
    )
    from app.services import portfolio_snapshot_service as pss

    mock_delay = MagicMock()
    monkeypatch.setattr(pss.capture_portfolio_snapshot, "delay", mock_delay)

    redis_client = MagicMock()
    # primera llamada NX ok; segunda None
    redis_client.set.side_effect = [True, None]
    monkeypatch.setattr(
        "redis.Redis.from_url",
        lambda *_a, **_k: redis_client,
    )

    assert pss.enqueue_startup_portfolio_snapshot() is True
    assert pss.enqueue_startup_portfolio_snapshot() is False
    mock_delay.assert_called_once_with()
