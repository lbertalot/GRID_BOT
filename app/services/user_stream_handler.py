from __future__ import annotations

import asyncio
from typing import Any, Dict

from app.services.binance_user_stream import BinanceUserStreamHandler
from app.core.operation_tracker import OperationTracker, OperationStatus


def map_execution_report_to_status(event: Dict[str, Any]) -> OperationStatus | None:
    """Mapea Binance executionReport a OperationStatus interno."""
    x = event.get("X")  # current order status
    if x == "NEW":
        return OperationStatus.ACCEPTED
    if x == "PARTIALLY_FILLED":
        return OperationStatus.PARTIALLY_FILLED
    if x == "FILLED":
        return OperationStatus.COMPLETED
    if x == "CANCELED":
        return OperationStatus.CANCELLED
    if x == "EXPIRED":
        return OperationStatus.EXPIRED
    if x == "REJECTED":
        return OperationStatus.FAILED
    return None


async def start_user_stream_and_track(api_key: str) -> None:
    tracker = OperationTracker()

    def _on_event(evt: Dict[str, Any]) -> None:
        try:
            client_order_id = evt.get("c")  # clientOrderId
            status = map_execution_report_to_status(evt)
            if not client_order_id or not status:
                return
            result = {
                "executed_price": float(evt.get("L") or 0.0),
                "executed_quantity": float(evt.get("l") or 0.0),
                "fees": 0.0,
                "exchange_status": evt.get("X"),
            }
            asyncio.create_task(tracker.update_operation_status(client_order_id, status, result))
        except Exception:
            pass

    stream = BinanceUserStreamHandler(api_key=api_key)
    # El handler nuevo expone `on_fill` (ejecuciones). Lo usamos como adapter del
    # callback `_on_event` para mantener la semántica de tracking existente.
    await stream.start(on_fill=_on_event)


