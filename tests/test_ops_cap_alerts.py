"""Unit tests del emit path ops cap / reserve (B20 / ADR-008).

Paper-safe: mockea Telegram; no toca exchange ni live.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

import pytest

from app.core.ops_cap_alerts import (
    KIND_CAP,
    KIND_RESERVE,
    emit_ops_cap_alerts,
    reset_ops_cap_alert_state,
)


@pytest.fixture(autouse=True)
def _reset_alert_state():
    reset_ops_cap_alert_state()
    yield
    reset_ops_cap_alert_state()


def _summary(**overrides):
    base = {
        "cap_exceeded": False,
        "reserve_exhausted_projection": False,
        "ops_burn_mtd": Decimal("5.00"),
        "monthly_cap": Decimal("10.00"),
        "projected_annual_burn": Decimal("60.00"),
        "ops_reserve_total": Decimal("100.00"),
        "month": "2026-08",
    }
    base.update(overrides)
    return base


def test_emit_sets_gauges_and_no_telegram_when_ok():
    from app.core.metrics import (
        ops_monthly_cap_exceeded,
        ops_reserve_exhausted_projection,
    )

    with patch("app.services.telegram_alert.send_telegram_alert") as tg:
        result = emit_ops_cap_alerts(_summary())

    assert result["cap_exceeded"] is False
    assert result["reserve_exhausted_projection"] is False
    assert result["fired_cap_exceeded"] is False
    assert result["fired_reserve_exhausted_projection"] is False
    assert ops_monthly_cap_exceeded._value.get() == 0
    assert ops_reserve_exhausted_projection._value.get() == 0
    tg.assert_not_called()


def test_emit_cap_exceeded_fires_telegram_and_counter_once():
    from app.core.metrics import (
        ops_cap_alerts_fired_total,
        ops_monthly_cap_exceeded,
    )

    before = ops_cap_alerts_fired_total.labels(kind=KIND_CAP)._value.get()

    with patch("app.services.telegram_alert.send_telegram_alert", return_value=True) as tg:
        first = emit_ops_cap_alerts(
            _summary(cap_exceeded=True, ops_burn_mtd=Decimal("18.00"))
        )
        second = emit_ops_cap_alerts(
            _summary(cap_exceeded=True, ops_burn_mtd=Decimal("18.00"))
        )

    assert first["fired_cap_exceeded"] is True
    assert second["fired_cap_exceeded"] is False
    assert ops_monthly_cap_exceeded._value.get() == 1
    assert ops_cap_alerts_fired_total.labels(kind=KIND_CAP)._value.get() == before + 1
    assert tg.call_count == 1
    assert "OPS CAP EXCEDIDO" in tg.call_args[0][0]


def test_emit_reserve_exhausted_fires_telegram_and_counter_once():
    from app.core.metrics import (
        ops_cap_alerts_fired_total,
        ops_reserve_exhausted_projection,
    )

    before = ops_cap_alerts_fired_total.labels(kind=KIND_RESERVE)._value.get()

    with patch("app.services.telegram_alert.send_telegram_alert", return_value=True) as tg:
        first = emit_ops_cap_alerts(
            _summary(
                reserve_exhausted_projection=True,
                projected_annual_burn=Decimal("144.00"),
            )
        )
        second = emit_ops_cap_alerts(
            _summary(
                reserve_exhausted_projection=True,
                projected_annual_burn=Decimal("144.00"),
            )
        )

    assert first["fired_reserve_exhausted_projection"] is True
    assert second["fired_reserve_exhausted_projection"] is False
    assert ops_reserve_exhausted_projection._value.get() == 1
    assert (
        ops_cap_alerts_fired_total.labels(kind=KIND_RESERVE)._value.get() == before + 1
    )
    assert tg.call_count == 1
    assert "RESERVA PROYECTADA AGOTADA" in tg.call_args[0][0]


def test_emit_refires_on_rising_edge_after_clear():
    with patch("app.services.telegram_alert.send_telegram_alert", return_value=True) as tg:
        emit_ops_cap_alerts(_summary(cap_exceeded=True))
        emit_ops_cap_alerts(_summary(cap_exceeded=False))
        emit_ops_cap_alerts(_summary(cap_exceeded=True))

    assert tg.call_count == 2


def test_emit_tolerates_missing_telegram_creds():
    """Sin TELEGRAM_* el notifier retorna False; el emit no debe fallar."""
    with patch(
        "app.services.telegram_alert.send_telegram_alert", return_value=False
    ) as tg:
        result = emit_ops_cap_alerts(_summary(cap_exceeded=True))

    assert result["fired_cap_exceeded"] is True
    tg.assert_called_once()


def test_prometheus_rule_file_declares_expected_alerts():
    from pathlib import Path

    rules = Path(__file__).resolve().parents[1] / (
        "docker/prometheus/rules/ops_cap_rules.yml"
    )
    text = rules.read_text(encoding="utf-8")
    assert "OpsMonthlyCapExceeded" in text
    assert "OpsReserveExhaustedProjection" in text
    assert "ops_monthly_cap_exceeded == 1" in text
    assert "ops_reserve_exhausted_projection == 1" in text
