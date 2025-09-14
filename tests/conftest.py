import os
import time
import requests
import pytest

@pytest.fixture(scope="session", autouse=True)
def wait_api_ready():
    base_url = os.getenv("GRIDBOT_BASE_URL", "http://localhost:8000")
    deadline = time.time() + 45
    last_err = None
    while time.time() < deadline:
        try:
            r = requests.get(f"{base_url}/health", timeout=5)
            if r.status_code == 200:
                return
        except Exception as e:
            last_err = e
        time.sleep(2)
    raise RuntimeError(f"API no disponible en {base_url} tras espera: {last_err}")
