from __future__ import annotations

import asyncio

from app.core.operation_tracker import OperationTracker  # type: ignore


async def run_operation_tracking_forever(interval_seconds: int = 30) -> None:
    tracker = OperationTracker()
    while True:
        try:
            await tracker.force_operation_check()
        except Exception:
            pass
        await asyncio.sleep(interval_seconds)
