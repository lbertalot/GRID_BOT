"""Liquidez del ciclo de trading: paper ledger SoT vs exchange.

S-PAPER-ISO follow-up (E-FILL-LIQ): `execute_trading_cycle` no debe usar el
balance spot de Binance (a menudo 0 USDT en keys read-only) cuando el modo
efectivo es paper — el cash del `PaperEquityLedger` es la fuente de verdad.
"""

from __future__ import annotations

import logging
from decimal import ROUND_DOWN, Decimal
from typing import Tuple

logger = logging.getLogger(__name__)

ZERO = Decimal("0")


def _as_decimal(value: object, *, default: Decimal = ZERO) -> Decimal:
    if value is None:
        return default
    try:
        return Decimal(str(value))
    except Exception:
        return default


def resolve_available_usdt_for_cycle(exchange_usdt: object) -> Tuple[Decimal, str]:
    """Resuelve USDT disponible para el gate de liquidez del ciclo.

    Returns:
        (available_usdt, source) con source en ``paper_ledger`` | ``exchange``.
    """
    exchange = _as_decimal(exchange_usdt)

    try:
        from app.core.paper_equity_ledger import (
            get_paper_ledger,
            paper_equity_is_source_of_truth,
        )
    except Exception as exc:  # pragma: no cover — import fail → exchange
        logger.warning("[paper-liq] no se pudo importar ledger: %s", exc)
        return exchange, "exchange"

    if not paper_equity_is_source_of_truth():
        return exchange, "exchange"

    try:
        cash = get_paper_ledger().cash
        paper_cash = _as_decimal(cash)
        logger.info(
            "[paper-liq] gate liquidez usa ledger cash=%s (exchange usdt=%s)",
            paper_cash,
            exchange,
        )
        return paper_cash, "paper_ledger"
    except Exception as exc:
        logger.warning(
            "[paper-liq] ledger cash no disponible (%s); fallback exchange=%s",
            exc,
            exchange,
        )
        try:
            from app.core.paper_trading import get_paper_portfolio_summary

            summary = get_paper_portfolio_summary() or {}
            bal = _as_decimal(summary.get("current_balance"), default=exchange)
            return bal, "paper_ledger"
        except Exception as exc2:
            logger.warning("[paper-liq] paper portfolio fallback falló: %s", exc2)
            return exchange, "exchange"


def should_skip_exchange_rebalancer(*, liquidity_source: str) -> bool:
    """En paper no rebalancear contra Binance para 'generar' USDT."""
    return liquidity_source == "paper_ledger"


def build_paper_balances_from_ledger(
    *, symbols: list[str] | None = None
) -> dict[str, float]:
    """Balances sintéticos paper: USDT=cash ledger + base = posición abierta.

    Permite BUY en cuenta flat (cash>0, ETH=0) sin leer spot Binance.
    """
    from app.core.paper_equity_ledger import get_paper_ledger

    ledger = get_paper_ledger()
    balances: dict[str, float] = {"USDT": float(ledger.cash)}
    syms = symbols or list(ledger.symbols())
    for symbol in syms:
        sym = str(symbol).upper()
        if not sym.endswith("USDT"):
            continue
        base = sym[:-4]
        qty = float(ledger.position(sym))
        if qty > 0:
            balances[base] = balances.get(base, 0.0) + qty
    return balances


def can_afford_grid_quantity(
    *,
    balances: dict[str, float],
    base_asset: str,
    quantity: float,
    price: float,
    paper_mode: bool,
) -> bool:
    """En paper: USDT ≥ notional **o** base ≥ qty. En exchange: base ≥ qty (legacy)."""
    if quantity <= 0 or price <= 0:
        return False
    base_bal = float(balances.get(base_asset, 0) or 0)
    if base_bal >= quantity:
        return True
    if paper_mode:
        usdt = float(balances.get("USDT", 0) or 0)
        return usdt >= quantity * price
    return False


def resolve_last_grid_action(
    symbol: str, *, fallback: str | None = None
) -> str | None:
    """Última acción de grid para anti-repetición.

    En paper SoT lee el último fill del ledger (persiste entre ciclos Celery).
    Sin esto ``AssetConfig.last_action`` nace siempre ``None`` al recrear el
    manager → solo BUY (80× observado 2026-08-08).
    """
    try:
        from app.core.paper_equity_ledger import (
            get_paper_ledger,
            paper_equity_is_source_of_truth,
        )

        if not paper_equity_is_source_of_truth():
            return fallback
        sym = str(symbol).upper()
        fills = [f for f in get_paper_ledger().fills if str(f.symbol).upper() == sym]
        if not fills:
            return fallback
        side = str(fills[-1].side or "").upper()
        if side in ("BUY", "SELL"):
            return side
        return fallback
    except Exception as exc:  # noqa: BLE001
        logger.warning("[paper-liq] resolve_last_grid_action falló: %s", exc)
        return fallback


def resolve_last_grid_level(
    symbol: str, *, fallback: float | None = None
) -> float | None:
    """Precio del último fill paper → ancla ``last_level`` (Δnivel ≥ 1).

    MM 2026-08-26: sin este ancla, ``decide_grid_action`` no puede exigir
    cruce de nivel tras BUY y vuelve a round-trips intra-nivel.
    """
    try:
        from app.core.paper_equity_ledger import (
            get_paper_ledger,
            paper_equity_is_source_of_truth,
        )

        if not paper_equity_is_source_of_truth():
            return fallback
        sym = str(symbol).upper()
        fills = [f for f in get_paper_ledger().fills if str(f.symbol).upper() == sym]
        if not fills:
            return fallback
        price = getattr(fills[-1], "price", None)
        if price is None:
            return fallback
        return float(price)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[paper-liq] resolve_last_grid_level falló: %s", exc)
        return fallback


def should_enforce_level_notional_on_sell(*, paper: bool) -> bool:
    """Piso L0 (15/20 USDT) es para BUY/nuevos niveles, no para cerrar inventario paper."""
    return not bool(paper)


def _floor_to_step(qty: Decimal, step: Decimal) -> Decimal:
    if step <= ZERO:
        return qty
    return (qty / step).to_integral_value(rounding=ROUND_DOWN) * step


def clip_paper_sell_quantity(
    *,
    symbol: str,
    sizer_qty: Decimal,
    step_size: Decimal | None = None,
) -> Decimal:
    """Clip SELL paper a ``min(sizer, ledger.position)`` con floor a ``step_size``.

    Fuera de paper SoT no recorta: devuelve ``sizer_qty`` tal cual.
    """
    sizer = _as_decimal(sizer_qty)

    try:
        from app.core.paper_equity_ledger import (
            get_paper_ledger,
            paper_equity_is_source_of_truth,
        )
    except Exception as exc:  # pragma: no cover — import fail → no clip
        logger.warning("[paper-liq] clip SELL: no se pudo importar ledger: %s", exc)
        return sizer

    if not paper_equity_is_source_of_truth():
        return sizer

    try:
        pos = _as_decimal(get_paper_ledger().position(symbol))
    except Exception as exc:
        logger.warning("[paper-liq] clip SELL: position() falló (%s); qty=0", exc)
        return ZERO

    qty = min(sizer, pos)
    step = _as_decimal(step_size) if step_size is not None else ZERO
    if step > ZERO:
        qty = _floor_to_step(qty, step)
    if qty <= ZERO:
        return ZERO
    logger.info(
        "[paper-liq] clip SELL %s sizer=%s pos=%s step=%s → qty=%s",
        symbol,
        sizer,
        pos,
        step,
        qty,
    )
    return qty


__all__ = [
    "resolve_available_usdt_for_cycle",
    "should_skip_exchange_rebalancer",
    "build_paper_balances_from_ledger",
    "can_afford_grid_quantity",
    "resolve_last_grid_action",
    "should_enforce_level_notional_on_sell",
    "clip_paper_sell_quantity",
]
