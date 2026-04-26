import asyncio

from app.services.binance_data_sync import BinanceDataSync


class _FakeConn:
    def __init__(self) -> None:
        self.inserted_order_ids = set()

    async def execute(self, query, *args):
        q = " ".join(str(query).split()).lower()
        if "insert into trades" in q:
            order_id = args[4]
            if order_id in self.inserted_order_ids:
                return "INSERT 0 0"
            self.inserted_order_ids.add(order_id)
            return "INSERT 0 1"
        return "OK"

    async def fetchrow(self, query, *args):
        if "select id from trades where order_id" in str(query).lower():
            order_id = args[0]
            if order_id in self.inserted_order_ids:
                return {"id": 1}
        return None

    async def close(self):
        return None


def test_sync_recent_trades_deduplicates_on_second_run(monkeypatch):
    sync = BinanceDataSync()
    fake_conn = _FakeConn()

    async def _fake_db_connection():
        return fake_conn

    class _FakeClient:
        def get_recent_trades(self, symbol, limit):
            return [
                {"id": 111, "isBuyerMaker": False, "qty": "0.01", "price": "100.0", "time": 1700000000000},
                {"id": 222, "isBuyerMaker": True, "qty": "0.02", "price": "101.0", "time": 1700000001000},
            ]

    sync.client = _FakeClient()
    monkeypatch.setattr(sync, "get_db_connection", _fake_db_connection)

    first = asyncio.run(sync.sync_recent_trades(symbol="BTCUSDT", limit=2))
    second = asyncio.run(sync.sync_recent_trades(symbol="BTCUSDT", limit=2))

    assert first["status"] == "success"
    assert first["trades_inserted"] == 2
    assert second["status"] == "success"
    assert second["trades_inserted"] == 0

