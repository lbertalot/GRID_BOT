from fastapi.testclient import TestClient
from app.main import app


def test_metrics_endpoint_smoke():
    client = TestClient(app)
    r = client.get("/metrics")
    assert r.status_code in (200, 401)
