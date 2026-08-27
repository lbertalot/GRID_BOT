from types import SimpleNamespace

import pytest

from app.core.system_integrity_state import (
    SystemIntegrityState,
    allows_order,
    operational_state,
)


def test_legacy_active_record_hydrates_reduce_only() -> None:
    assert operational_state(SimpleNamespace(active=True, operational_state=None)) == (
        SystemIntegrityState.REDUCE_ONLY
    )


def test_legacy_inactive_record_hydrates_closed() -> None:
    assert operational_state(SimpleNamespace(active=False, operational_state=None)) == (
        SystemIntegrityState.CLOSED
    )


def test_reduce_only_allows_only_marked_sell() -> None:
    assert allows_order(
        state=SystemIntegrityState.REDUCE_ONLY, side="SELL", reduce_only=True
    )
    assert not allows_order(
        state=SystemIntegrityState.REDUCE_ONLY, side="BUY", reduce_only=True
    )
    assert not allows_order(
        state=SystemIntegrityState.REDUCE_ONLY, side="SELL", reduce_only=False
    )
    assert not allows_order(
        state=SystemIntegrityState.REDUCE_ONLY, side="SELL", reduce_only="true"
    )


def test_unknown_state_fails_closed() -> None:
    with pytest.raises(ValueError, match="inválido"):
        operational_state({"active": True, "operational_state": "unknown"})
