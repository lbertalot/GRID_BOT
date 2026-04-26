from fastapi.testclient import TestClient
from app.main import app


def test_get_price_endpoint():
    client = TestClient(app)
    r = client.get("/price/BTCUSDT")
    assert r.status_code in (200, 400)
    if r.status_code == 200:
        data = r.json()
        assert data["symbol"] == "BTCUSDT"
        assert "price" in data
