import asyncio
import pytest
from app.core.operation_tracker import OperationTracker, OperationStatus


@pytest.mark.asyncio
async def test_track_and_update_operation_flow():
    ot = OperationTracker()
    op_id = await ot.track_operation({
        'asset': 'BTCUSDT',
        'type': 'MARKET',
        'side': 'BUY',
        'quantity': 0.001,
        'price': 50000.0,
        'metadata': {}
    })
    assert op_id in ot.active_operations
    await ot.update_operation_status(op_id, OperationStatus.SUBMITTED, {'exchange_status': 'NEW'})
    await ot.update_operation_status(op_id, OperationStatus.ACCEPTED, {'exchange_status': 'ACK'})
    await ot.update_operation_status(op_id, OperationStatus.COMPLETED, {'executed_price': 50010.0, 'executed_quantity': 0.001, 'fees': 0.0001})
    assert op_id not in ot.active_operations


