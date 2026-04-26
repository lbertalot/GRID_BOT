from __future__ import annotations

from typing import Any, Dict

from fastapi import Depends, HTTPException

from app.services.order_validation import OrderValidator  # type: ignore
from app.services.binance_client_singleton import get_binance_client_singleton  # type: ignore
from app.core.metrics import order_validation_rejects_total  # type: ignore


def get_order_validator() -> OrderValidator:
    client_singleton = get_binance_client_singleton()
    return OrderValidator(client_singleton.client)


async def validate_order_e2e(
    symbol: str,
    side: str,
    order_type: str,
    quantity: float,
    price: float | None = None,
    validator: OrderValidator = Depends(get_order_validator),
) -> Dict[str, Any]:
    validation = validator.validate_order_parameters(
        symbol, quantity, side, order_type, price
    )
    if not validation.get("is_valid"):
        reason = "|".join(validation.get("errors", [])[:1]) or "invalid_order"
        try:
            order_validation_rejects_total.labels(reason=reason, symbol=symbol).inc()
        except Exception:
            pass
        raise HTTPException(
            status_code=400,
            detail={"status": "rejected", "reason": reason, "validation": validation},
        )
    return validation
