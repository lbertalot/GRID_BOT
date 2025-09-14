import os
import requests

BASE_URL = os.getenv("GRIDBOT_BASE_URL", "http://localhost:8000")

def test_read_root():
    r = requests.get(f"{BASE_URL}/", timeout=10)
    assert r.status_code == 200
    js = r.json()
    assert js.get("status") == "running"