"""Órdenes BUY pendientes paper-sim (IC-A).

En paper el exchange simulado no tenía book de límites: IC-1 bloqueaba BUY
nuevos pero no podía cancelar resting. Este módulo es el SoT in-process de
órdenes BUY abiertas paper-only.

**PROMOTE_LIVE: NO** — no toca exchange real.
"""

from __future__ import annotations

import itertools
import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_id_seq = itertools.count(1)
_lock = threading.RLock()


@dataclass
class PaperPendingOrder:
    order_id: int
    symbol: str
    side: str
    price: Decimal
    quantity: Decimal
    status: str = "NEW"
    created_at: str = ""

    def as_binance_dict(self) -> Dict[str, Any]:
        return {
            "orderId": self.order_id,
            "symbol": self.symbol,
            "side": self.side,
            "status": self.status,
            "price": str(self.price),
            "origQty": str(self.quantity),
            "executedQty": "0",
            "type": "LIMIT",
            "timeInForce": "GTC",
            "paper_only": True,
        }


class PaperPendingOrderBook:
    """Book in-memory de límites paper (BUY focus para IC-1)."""

    def __init__(self) -> None:
        self._orders: Dict[int, PaperPendingOrder] = {}

    def add_buy(
        self,
        *,
        symbol: str,
        price: Any,
        quantity: Any,
        order_id: Optional[int] = None,
    ) -> PaperPendingOrder:
        with _lock:
            oid = int(order_id) if order_id is not None else next(_id_seq)
            order = PaperPendingOrder(
                order_id=oid,
                symbol=str(symbol).upper(),
                side="BUY",
                price=Decimal(str(price)),
                quantity=Decimal(str(quantity)),
                status="NEW",
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            self._orders[oid] = order
            return order

    def list_open(
        self,
        *,
        symbol: Optional[str] = None,
        side: Optional[str] = None,
    ) -> List[PaperPendingOrder]:
        with _lock:
            out: List[PaperPendingOrder] = []
            for o in self._orders.values():
                if o.status != "NEW":
                    continue
                if symbol and o.symbol != str(symbol).upper():
                    continue
                if side and o.side != str(side).upper():
                    continue
                out.append(o)
            return out

    def cancel(self, order_id: int) -> Optional[PaperPendingOrder]:
        with _lock:
            order = self._orders.get(int(order_id))
            if order is None or order.status != "NEW":
                return None
            order.status = "CANCELED"
            return order

    def cancel_buys(
        self,
        *,
        symbol: Optional[str] = None,
        reason: str = "IC1_stop_rebuy_outside_range",
    ) -> List[Dict[str, Any]]:
        """Cancela todas las BUY NEW (opcionalmente filtradas por símbolo)."""
        canceled: List[Dict[str, Any]] = []
        for order in list(self.list_open(symbol=symbol, side="BUY")):
            gone = self.cancel(order.order_id)
            if gone is None:
                continue
            payload = gone.as_binance_dict()
            payload["cancel_reason"] = reason
            canceled.append(payload)
        if canceled:
            logger.warning(
                "[IC-1] cancel-all BUY paper sim n=%s symbol=%s reason=%s",
                len(canceled),
                symbol or "*",
                reason,
            )
        return canceled

    def clear(self) -> None:
        with _lock:
            self._orders.clear()


_shared_book: Optional[PaperPendingOrderBook] = None


def get_paper_pending_order_book() -> PaperPendingOrderBook:
    global _shared_book
    if _shared_book is None:
        _shared_book = PaperPendingOrderBook()
    return _shared_book


def reset_paper_pending_order_book() -> PaperPendingOrderBook:
    """Solo tests."""
    global _shared_book
    _shared_book = PaperPendingOrderBook()
    return _shared_book


def cancel_pending_buys_paper(
    *,
    symbol: Optional[str] = None,
    reason: str = "IC1_stop_rebuy_outside_range",
) -> List[Dict[str, Any]]:
    return get_paper_pending_order_book().cancel_buys(symbol=symbol, reason=reason)


__all__ = [
    "PaperPendingOrder",
    "PaperPendingOrderBook",
    "get_paper_pending_order_book",
    "reset_paper_pending_order_book",
    "cancel_pending_buys_paper",
]
