from unittest.mock import patch
from app.services.binance_service import BinanceService


def test_get_account_retries_with_backoff(monkeypatch):
    svc = BinanceService()
    svc.simulation_mode = False

    class _Err(Exception):
        pass

    calls = {"n": 0}

    def _raise_then_success(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] < 3:
            raise _Err("transient")
        return {"balances": []}

    with patch.object(svc.client, "get_account", side_effect=_raise_then_success):
        data = svc.get_account_info()
        assert "balances" in data
        assert calls["n"] >= 3
