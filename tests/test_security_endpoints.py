import os
import requests

BASE_URL = os.getenv("GRIDBOT_BASE_URL", "http://localhost:8000")


def test_trades_requires_auth():
    r = requests.get(f"{BASE_URL}/trades", timeout=5)
    assert r.status_code in (401, 404)


def test_grid_config_requires_auth():
    r = requests.get(f"{BASE_URL}/grid_config", timeout=5)
    assert r.status_code in (401, 404)


def test_metrics_update_pnl_requires_auth():
    r = requests.post(f"{BASE_URL}/api/metrics/update-pnl", timeout=5)
    assert r.status_code in (401, 404)
