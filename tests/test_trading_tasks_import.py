"""Carga del módulo trading_tasks para cobertura de nivel módulo (imports y constantes)."""


def test_trading_tasks_module_exposes_risk_constants() -> None:
    from app.services import trading_tasks as tt

    assert tt.MIN_NOTIONAL_USDT > 0
    assert tt.SAFE_MIN_USDT >= tt.MIN_NOTIONAL_USDT
    assert 0 < tt.MIN_DECISION_CONFIDENCE < 1.0
    assert isinstance(tt.CALIBRATION_MODE, bool)
    assert tt.BALANCES_CACHE_KEY
