import os
import pytest
import requests

BASE_URL = os.getenv("GRIDBOT_BASE_URL", "http://localhost:8000")


def test_trades_requires_auth():
    r = requests.get(f"{BASE_URL}/trade/trades", timeout=5)
    assert r.status_code == 401


def test_grid_config_requires_auth():
    r = requests.get(f"{BASE_URL}/trade/grid_config", timeout=5)
    assert r.status_code == 401


def test_metrics_update_pnl_requires_auth():
    r = requests.post(f"{BASE_URL}/api/metrics/update-pnl", timeout=5)
    assert r.status_code == 401


