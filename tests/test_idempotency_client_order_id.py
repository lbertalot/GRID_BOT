from app.core.operation_tracker import OperationTracker


def test_client_order_id_is_stable():
    ot = OperationTracker()
    args = {
        "asset": "BTCUSDT",
        "side": "BUY",
        "quantity": "0.001",
        "price": "50000.0",
        "metadata": "{}",
    }
    cid1 = ot.generate_client_order_id(**args)
    cid2 = ot.generate_client_order_id(**args)
    assert cid1 == cid2
    assert cid1.startswith("GRIDBOT_")
    assert len(cid1) == len("GRIDBOT_") + 24
