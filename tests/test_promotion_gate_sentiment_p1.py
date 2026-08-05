"""P1: lectura Redis/stub de sentimiento para el gate de promoción."""

from __future__ import annotations

import pytest

from app.services import promotion_gate_sentiment as pgs


@pytest.mark.asyncio
async def test_resolve_returns_redis_dict_score(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_get(key: str):
        assert "BTCUSDT" in key
        return {"score": -0.15}

    monkeypatch.setattr("app.core.redis_cache.redis_cache.get", fake_get)
    score = await pgs.resolve_promotion_gate_sentiment_score("btcusdt")
    assert score == pytest.approx(-0.15)


@pytest.mark.asyncio
async def test_resolve_clamps_score(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_get(_key: str):
        return {"score": 9.0}

    monkeypatch.setattr("app.core.redis_cache.redis_cache.get", fake_get)
    score = await pgs.resolve_promotion_gate_sentiment_score("ETHUSDT")
    assert score == 1.0


@pytest.mark.asyncio
async def test_resolve_stub_when_redis_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_get(_key: str):
        return None

    monkeypatch.setenv("ML_PROMOTION_GATE_NLP_STUB_SCORE", "0.33")
    monkeypatch.setattr("app.core.redis_cache.redis_cache.get", fake_get)
    score = await pgs.resolve_promotion_gate_sentiment_score("SOLUSDT")
    assert score == pytest.approx(0.33)


@pytest.mark.asyncio
async def test_resolve_empty_symbol_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ML_PROMOTION_GATE_NLP_STUB_SCORE", raising=False)
    score = await pgs.resolve_promotion_gate_sentiment_score("  ")
    assert score is None
