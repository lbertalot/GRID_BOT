import os
import requests

BASE_URL = os.getenv("GRIDBOT_BASE_URL", "http://localhost:8000")
API_KEY = os.getenv("API_KEY", "aPZGos-2ok2Cb9t0OeOMPzUqtMU0GPk0")


def test_order_market_buy_authenticated_minimal():
    url = f"{BASE_URL}/api/trade/order"
    headers = {"Authorization": f"Bearer {API_KEY}"}
    payload = {"symbol": "BTCUSDT", "side": "BUY", "quantity": 0.001, "type": "MARKET"}
    r = requests.post(url, json=payload, headers=headers, timeout=20)
    # En entorno productivo puede ser 200 (ejecución) o 400 (validación/notional), pero no 401
    assert r.status_code in (200, 400, 503)


def test_order_requires_auth():
    url = f"{BASE_URL}/api/trade/order"
    payload = {"symbol": "BTCUSDT", "side": "BUY", "quantity": 0.001, "type": "MARKET"}
    r = requests.post(url, json=payload, timeout=20)
    assert r.status_code in (401, 403)


def test_run_grid_authenticated():
    url = f"{BASE_URL}/api/trade/run_grid"
    headers = {"Authorization": f"Bearer {API_KEY}"}
    payload = {
        "symbol": "BTCUSDT",
        "min_price": 100.0,
        "max_price": 200000.0,
        "grids": 3,
        "quantity": 0.001,
        "last_action": None,
    }
    r = requests.post(url, json=payload, headers=headers, timeout=20)
    assert r.status_code in (200, 400, 503)


def test_strategy_scalping_live():
    url = f"{BASE_URL}/api/strategies/strategy/scalping"
    payload = {
        "symbol": "BTCUSDT",
        "interval": "1m",
        "limit": 3,
        "balances": {"USDT": 100},
        "params": {},
    }
    r = requests.post(url, json=payload, timeout=20)
    assert r.status_code in (200, 400)
    if r.status_code == 200:
        assert r.json().get("action") in ("BUY", "SELL", "HOLD")


def test_strategy_backtest_scalping_live():
    url = f"{BASE_URL}/api/strategies/strategy/backtest"
    params = {"strategy": "scalping"}
    payload = {
        "symbol": "BTCUSDT",
        "interval": "1m",
        "limit": 20,
        "balances": {"USDT": 100},
        "params": {},
    }
    r = requests.post(url, params=params, json=payload, timeout=30)
    assert r.status_code in (200, 400)
    if r.status_code == 200:
        data = r.json()
        assert isinstance(data, list)
        assert data and isinstance(data[-1], dict)
