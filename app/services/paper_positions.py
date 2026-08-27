"""Lectura paper-only de posiciones desde el ledger transaccional autoritativo."""
from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Callable, Mapping

from sqlalchemy import bindparam, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.metrics import (
    inventory_cap_usdt,
    inventory_cap_utilization_ratio,
    inventory_notional_usdt,
)
from app.models.paper_ledger import PaperLedgerCycle

ZERO = Decimal("0")
MarkProvider = Callable[[Session, tuple[str, ...]], Mapping[str, Decimal]]


class PaperPositionUnavailable(RuntimeError):
    """No se puede dar una posición valorada completa de forma segura."""


@dataclass(frozen=True)
class PaperPosition:
    symbol: str
    open_quantity: Decimal
    cost_basis_open_usdt: Decimal
    mark_price: Decimal
    market_value_usdt: Decimal
    unrealized_pnl_usdt: Decimal

    def to_dict(self) -> dict[str, str]:
        decimal_string = lambda value: format(value, "f")
        return {
            "symbol": self.symbol,
            "open_quantity": decimal_string(self.open_quantity),
            "cost_basis_open_usdt": decimal_string(self.cost_basis_open_usdt),
            "mark_price": decimal_string(self.mark_price),
            "market_value_usdt": decimal_string(self.market_value_usdt),
            "unrealized_pnl_usdt": decimal_string(self.unrealized_pnl_usdt),
        }


def _decimal(value: object, *, field_name: str) -> Decimal:
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise PaperPositionUnavailable(f"{field_name} inválido") from exc
    if not decimal_value.is_finite():
        raise PaperPositionUnavailable(f"{field_name} inválido")
    return decimal_value.normalize()


def _inventory_cap() -> Decimal:
    cap = _decimal(
        os.getenv("PAPER_DEPLOYED_CAPITAL_USDT", "200"),
        field_name="PAPER_DEPLOYED_CAPITAL_USDT",
    )
    if cap <= ZERO:
        raise PaperPositionUnavailable("PAPER_DEPLOYED_CAPITAL_USDT debe ser positivo")
    return cap


def get_latest_klines_marks(db: Session, symbols: tuple[str, ...]) -> Mapping[str, Decimal]:
    """Lee marks locales; nunca consulta un exchange ni acepta marks incompletos."""
    if not symbols:
        return {}
    try:
        rows = db.execute(
            text(
                """
                SELECT symbol, close_price
                FROM klines_data
                WHERE upper(symbol) IN :symbols
                ORDER BY open_time DESC
                """
            ).bindparams(bindparam("symbols", expanding=True, value=list(symbols)))
        )
    except SQLAlchemyError as exc:
        raise PaperPositionUnavailable("marks paper no disponibles") from exc

    marks: dict[str, Decimal] = {}
    for row in rows.mappings():
        symbol = str(row["symbol"]).upper()
        if symbol not in marks:
            mark = _decimal(row["close_price"], field_name=f"mark[{symbol}]")
            if mark <= ZERO:
                raise PaperPositionUnavailable(f"mark inválido para {symbol}")
            marks[symbol] = mark
    missing = sorted(set(symbols) - set(marks))
    if missing:
        raise PaperPositionUnavailable(
            f"mark no disponible para {', '.join(missing)}; valoración rechazada"
        )
    return marks


def _publish_inventory_cap(*, notional: Decimal, cap: Decimal) -> None:
    inventory_notional_usdt.set(float(notional))
    inventory_cap_usdt.set(float(cap))
    inventory_cap_utilization_ratio.set(float(notional / cap))


def read_paper_positions(
    db: Session, *, mark_provider: MarkProvider = get_latest_klines_marks
) -> tuple[PaperPosition, ...]:
    """Devuelve posiciones abiertas valoradas o falla cerrada ante marks faltantes."""
    try:
        cycles = (
            db.query(PaperLedgerCycle)
            .filter(PaperLedgerCycle.open_quantity > ZERO)
            .order_by(PaperLedgerCycle.symbol.asc(), PaperLedgerCycle.opened_at.asc())
            .all()
        )
    except SQLAlchemyError as exc:
        raise PaperPositionUnavailable("ledger paper no disponible") from exc
    if not cycles:
        cap = _inventory_cap()
        _publish_inventory_cap(notional=ZERO, cap=cap)
        return ()

    quantities: dict[str, Decimal] = {}
    costs: dict[str, Decimal] = {}
    for cycle in cycles:
        symbol = str(cycle.symbol).upper()
        quantities[symbol] = quantities.get(symbol, ZERO) + _decimal(
            cycle.open_quantity, field_name=f"open_quantity[{symbol}]"
        )
        costs[symbol] = costs.get(symbol, ZERO) + _decimal(
            cycle.cost_basis_open_usdt, field_name=f"cost_basis_open_usdt[{symbol}]"
        )

    total_cost = sum(costs.values(), ZERO)
    cap = _inventory_cap()
    _publish_inventory_cap(notional=total_cost, cap=cap)
    marks = mark_provider(db, tuple(sorted(quantities)))
    positions = []
    for symbol in sorted(quantities):
        mark = _decimal(marks.get(symbol), field_name=f"mark[{symbol}]")
        if mark <= ZERO:
            raise PaperPositionUnavailable(f"mark inválido para {symbol}")
        market_value = quantities[symbol] * mark
        positions.append(
            PaperPosition(
                symbol=symbol,
                open_quantity=quantities[symbol],
                cost_basis_open_usdt=costs[symbol],
                mark_price=mark,
                market_value_usdt=market_value,
                unrealized_pnl_usdt=market_value - costs[symbol],
            )
        )
    return tuple(positions)
