import os
import requests

BASE_URL = os.getenv("GRIDBOT_BASE_URL", "http://localhost:8000")


def test_metrics_path_normalized_smoke():
    # No valida exactamente las etiquetas, pero verifica que /metrics esté vivo
    r = requests.get(f"{BASE_URL}/metrics", timeout=5)
    assert r.status_code in (200, 401)
