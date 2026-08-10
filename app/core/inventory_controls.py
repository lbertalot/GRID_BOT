"""IC-1 / IC-2 — contención de inventario del book Core (desk-policy-l0 §2.5).

Paper-first. Este módulo **no** habilita live ni cambia sizing.

- **IC-1** (`IC1_stop_rebuy_outside_range`): si mid < piso del rango (−5% freeze),
  deja de reponer compras del Core.
- **IC-2** (`IC2_flatten_core_at_deployed_dd_pct`): si el DD MtM del Core desde
  pico ≥ umbral % del capital **desplegado** (default 10% → −USD 20 con 200),
  aplana el book Core y desarma hasta diagnóstico escrito.

Evaluación pura en Decimal; enforce inyectable (tests sin side-effects de red).
Slice E7 IC-WIRE · deadline ≤ 2026-08-13.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, DecimalException
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Protocol

logger = logging.getLogger(__name__)

ZERO = Decimal("0")
HUNDRED = Decimal("100")
DEFAULT_DEPLOYED = Decimal("200")
DEFAULT_IC2_THRESHOLD_PCT = Decimal("10.00")
EVENT_IC1 = "IC1_stop_rebuy_outside_range"
EVENT_IC2 = "IC2_flatten_core_at_deployed_dd"
BREAKER_REASON_IC2 = "IC2_flatten_core_at_deployed_dd"


class InventoryControlInputError(ValueError):
    """Input inválido: fallar cerrado antes que asumir."""


def _to_decimal(value: Any, field_name: str) -> Decimal:
    if value is None or (isinstance(value, str) and not value.strip()):
        raise InventoryControlInputError(
            f"{field_name} es requerido y no puede ser vacío"
        )
    if isinstance(value, Decimal):
        candidate = value
    elif isinstance(value, (int, str)):
        try:
            candidate = Decimal(str(value).strip())
        except (DecimalException, ValueError) as exc:
            raise InventoryControlInputError(
                f"{field_name} no es numérico: {value!r}"
            ) from exc
    elif isinstance(value, float):
        candidate = Decimal(str(value))
    else:
        raise InventoryControlInputError(
            f"{field_name} tipo no soportado: {type(value)!r}"
        )
    return candidate


@dataclass(frozen=True)
class IcControlsConfig:
    """Parámetros IC desde freeze L0 (metadata + rango del símbolo activo)."""

    enabled_ic1: bool = True
    enabled_ic2: bool = True
    symbol: str = "ETHUSDT"
    range_floor: Optional[Decimal] = None
    range_ceiling: Optional[Decimal] = None
    deployed_capital: Decimal = DEFAULT_DEPLOYED
    ic2_threshold_pct: Decimal = DEFAULT_IC2_THRESHOLD_PCT

    @property
    def ic2_threshold_fraction(self) -> Decimal:
        return self.ic2_threshold_pct / HUNDRED


@dataclass
class InventoryControlState:
    """Estado runtime paper-safe (no persiste en Redis aún — E7 stub)."""

    ic1_active: bool = False
    ic2_active: bool = False
    flatten_pending: bool = False
    armed: bool = True  # False tras IC-2 hasta re-arm manual
    last_mid: Optional[Decimal] = None
    last_equity: Optional[Decimal] = None
    peak_equity: Optional[Decimal] = None
    last_events: List[Dict[str, Any]] = field(default_factory=list)
    updated_at: Optional[datetime] = None


@dataclass(frozen=True)
class InventoryControlDecision:
    """Resultado de una evaluación (observable + enforceable)."""

    ic1_active: bool
    ic2_should_flatten: bool
    events: tuple[Dict[str, Any], ...]
    mid: Optional[Decimal] = None
    equity_mtm: Optional[Decimal] = None
    peak_equity: Optional[Decimal] = None
    dd_pct_deployed: Optional[Decimal] = None


def evaluate_ic1_stop_rebuy(
    *,
    mid: Any,
    range_floor: Any,
) -> bool:
    """True ⇒ freno de carga: no reponer BUY bajo el piso del rango."""
    mid_d = _to_decimal(mid, "mid")
    floor_d = _to_decimal(range_floor, "range_floor")
    if mid_d <= ZERO or floor_d <= ZERO:
        raise InventoryControlInputError("mid y range_floor deben ser > 0")
    return mid_d < floor_d


def evaluate_ic2_flatten(
    *,
    equity_mtm: Any,
    peak_equity: Any,
    deployed_capital: Any = DEFAULT_DEPLOYED,
    threshold_pct: Any = DEFAULT_IC2_THRESHOLD_PCT,
) -> tuple[bool, Decimal]:
    """True si DD desde pico ≥ threshold% del desplegado.

    Alineado al rojo MaxDD desk §3.3 / L0 §2.2: mismo número que corta y rechaza.
    Retorna (should_flatten, dd_pct_deployed).
    """
    equity = _to_decimal(equity_mtm, "equity_mtm")
    peak = _to_decimal(peak_equity, "peak_equity")
    deployed = _to_decimal(deployed_capital, "deployed_capital")
    thr = _to_decimal(threshold_pct, "threshold_pct")
    if deployed <= ZERO:
        raise InventoryControlInputError("deployed_capital debe ser > 0")
    if thr <= ZERO:
        raise InventoryControlInputError("threshold_pct debe ser > 0")
    if peak < equity:
        peak = equity
    dd_usdt = peak - equity
    dd_pct = dd_usdt / deployed
    return dd_pct >= (thr / HUNDRED), dd_pct


def load_ic_controls_from_grid_config(
    path: Optional[str | Path] = None,
) -> IcControlsConfig:
    """Lee `ic_controls` + min/max del símbolo activo desde GRID_CONFIG_FILE."""
    cfg_path = Path(
        path
        or os.getenv("GRID_CONFIG_FILE", "grid_config_paper_l0.json")
    )
    try:
        raw = json.loads(cfg_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 — fail-soft a defaults paper
        logger.warning(
            "[IC] No se pudo leer %s (%s); defaults paper IC enabled",
            cfg_path,
            exc,
        )
        return IcControlsConfig()

    if not isinstance(raw, Mapping):
        return IcControlsConfig()

    meta = raw.get("_config_metadata") or {}
    ic = meta.get("ic_controls") or {}
    enabled_ic1 = bool(ic.get("IC1_stop_rebuy_outside_range", True))
    thr_raw = ic.get("IC2_flatten_core_at_deployed_dd_pct", "10.00")
    try:
        thr = _to_decimal(thr_raw, "IC2_threshold")
        enabled_ic2 = thr > ZERO
    except InventoryControlInputError:
        thr = DEFAULT_IC2_THRESHOLD_PCT
        enabled_ic2 = True

    deployed = _to_decimal(
        meta.get("deployed_capital_usd", DEFAULT_DEPLOYED), "deployed_capital_usd"
    )

    symbol = "ETHUSDT"
    range_floor: Optional[Decimal] = None
    range_ceiling: Optional[Decimal] = None
    for key, block in raw.items():
        if key.startswith("_") or not isinstance(block, Mapping):
            continue
        if not block.get("is_active", False):
            continue
        symbol = str(block.get("symbol") or key).upper()
        if block.get("min_price") is not None:
            range_floor = _to_decimal(block["min_price"], "min_price")
        if block.get("max_price") is not None:
            range_ceiling = _to_decimal(block["max_price"], "max_price")
        break

    return IcControlsConfig(
        enabled_ic1=enabled_ic1,
        enabled_ic2=enabled_ic2,
        symbol=symbol,
        range_floor=range_floor,
        range_ceiling=range_ceiling,
        deployed_capital=deployed,
        ic2_threshold_pct=thr,
    )


def _event(name: str, **payload: Any) -> Dict[str, Any]:
    return {
        "event": name,
        "at": datetime.now(timezone.utc).isoformat(),
        "paper_only": True,
        **payload,
    }


def _publish_metrics(state: InventoryControlState) -> None:
    try:
        from app.core import metrics as m

        if hasattr(m, "ic1_stop_rebuy_active"):
            m.ic1_stop_rebuy_active.set(1 if state.ic1_active else 0)
        if hasattr(m, "ic2_flatten_active"):
            m.ic2_flatten_active.set(1 if state.ic2_active else 0)
    except Exception as exc:  # noqa: BLE001
        logger.debug("[IC] metrics skip: %s", exc)


class FlattenPort(Protocol):
    def __call__(
        self,
        *,
        symbol: str,
        quantity: Decimal,
        price: Decimal,
    ) -> Any: ...


class InventoryControlGuard:
    """Observa marcas, emite eventos y enforce paper-safe (E7 + IC-A/B)."""

    def __init__(
        self,
        config: Optional[IcControlsConfig] = None,
        *,
        activate_breaker: Optional[Callable[[str, str], Any]] = None,
        flatten_sell: Optional[FlattenPort] = None,
        cancel_buys: Optional[Callable[..., Any]] = None,
    ) -> None:
        self.config = config or load_ic_controls_from_grid_config()
        self.state = InventoryControlState()
        self._activate_breaker = activate_breaker
        self._flatten_sell = flatten_sell
        self._cancel_buys = cancel_buys

    def allows_core_buy(self) -> bool:
        """Gate pre-orden BUY del Core: IC-1 activo, IC-2 o desarmado → no."""
        if not self.state.armed:
            return False
        if self.state.ic2_active or self.state.flatten_pending:
            return False
        if self.config.enabled_ic1 and self.state.ic1_active:
            return False
        return True

    def observe(
        self,
        *,
        mid: Optional[Any] = None,
        equity_mtm: Optional[Any] = None,
        peak_equity: Optional[Any] = None,
        range_floor: Optional[Any] = None,
        enforce: bool = True,
    ) -> InventoryControlDecision:
        """Actualiza estado desde una marca. `enforce=True` dispara flatten stub."""
        events: List[Dict[str, Any]] = []
        floor = range_floor if range_floor is not None else self.config.range_floor

        ic1 = False
        if self.config.enabled_ic1 and mid is not None and floor is not None:
            ic1 = evaluate_ic1_stop_rebuy(mid=mid, range_floor=floor)
            mid_d = _to_decimal(mid, "mid")
            self.state.last_mid = mid_d
            if ic1 and not self.state.ic1_active:
                ev = _event(
                    EVENT_IC1,
                    active=True,
                    mid=str(mid_d),
                    range_floor=str(_to_decimal(floor, "range_floor")),
                    symbol=self.config.symbol,
                )
                events.append(ev)
                logger.warning("[IC-1] %s mid=%s floor=%s", EVENT_IC1, mid_d, floor)
                try:
                    from app.core import metrics as m

                    if hasattr(m, "ic1_trips_total"):
                        m.ic1_trips_total.inc()
                except Exception:  # noqa: BLE001
                    pass
                if enforce:
                    self._enforce_ic1_cancel_buys()
            elif not ic1 and self.state.ic1_active:
                events.append(
                    _event(EVENT_IC1, active=False, mid=str(mid_d), recovered=True)
                )
                logger.info("[IC-1] rango recuperado mid=%s — rebuy permitido", mid_d)
            self.state.ic1_active = ic1

        ic2 = False
        dd_pct: Optional[Decimal] = None
        peak_d: Optional[Decimal] = None
        equity_d: Optional[Decimal] = None
        if (
            self.config.enabled_ic2
            and equity_mtm is not None
            and self.state.armed
        ):
            equity_d = _to_decimal(equity_mtm, "equity_mtm")
            self.state.last_equity = equity_d
            if peak_equity is not None:
                peak_d = _to_decimal(peak_equity, "peak_equity")
            elif self.state.peak_equity is not None:
                peak_d = max(self.state.peak_equity, equity_d)
            else:
                peak_d = equity_d
            self.state.peak_equity = peak_d
            ic2, dd_pct = evaluate_ic2_flatten(
                equity_mtm=equity_d,
                peak_equity=peak_d,
                deployed_capital=self.config.deployed_capital,
                threshold_pct=self.config.ic2_threshold_pct,
            )
            if ic2 and not self.state.ic2_active:
                ev = _event(
                    EVENT_IC2,
                    active=True,
                    equity_mtm=str(equity_d),
                    peak_equity=str(peak_d),
                    dd_pct_deployed=str(dd_pct),
                    deployed_capital=str(self.config.deployed_capital),
                    threshold_pct=str(self.config.ic2_threshold_pct),
                    symbol=self.config.symbol,
                )
                events.append(ev)
                logger.error(
                    "[IC-2] %s dd_pct_deployed=%s (thr=%s%%)",
                    EVENT_IC2,
                    dd_pct,
                    self.config.ic2_threshold_pct,
                )
                try:
                    from app.core import metrics as m

                    if hasattr(m, "ic2_trips_total"):
                        m.ic2_trips_total.inc()
                except Exception:  # noqa: BLE001
                    pass
                self.state.ic2_active = True
                self.state.flatten_pending = True
                if enforce:
                    self._enforce_ic2()

        self.state.last_events.extend(events)
        self.state.updated_at = datetime.now(timezone.utc)
        _publish_metrics(self.state)

        return InventoryControlDecision(
            ic1_active=self.state.ic1_active,
            ic2_should_flatten=self.state.ic2_active,
            events=tuple(events),
            mid=self.state.last_mid,
            equity_mtm=equity_d,
            peak_equity=peak_d,
            dd_pct_deployed=dd_pct,
        )

    def _enforce_ic1_cancel_buys(self) -> None:
        """IC-A: cancel-all BUY pendientes paper-sim al trip IC-1."""
        try:
            if self._cancel_buys is not None:
                canceled = self._cancel_buys(
                    symbol=self.config.symbol,
                    reason=EVENT_IC1,
                )
            else:
                from app.core.paper_pending_orders import cancel_pending_buys_paper

                canceled = cancel_pending_buys_paper(
                    symbol=self.config.symbol,
                    reason=EVENT_IC1,
                )
            n = len(canceled) if canceled is not None else 0
            self.state.last_events.append(
                _event(EVENT_IC1, cancel_buys=True, canceled_n=n)
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("[IC-1] cancel-all BUY paper falló: %s", exc)

    def _enforce_ic2(self) -> None:
        """Breaker + desarme; flatten_pending queda True hasta flatten_core_paper."""
        if self._activate_breaker is not None:
            try:
                self._activate_breaker("system_integrity", BREAKER_REASON_IC2)
            except Exception as exc:  # noqa: BLE001
                logger.error("[IC-2] no se pudo activar breaker: %s", exc)
        else:
            # Best-effort sync compartido (IC-C residual paper-safe).
            try:
                import asyncio
                import inspect

                from app.core.circuit_breakers import get_shared_breakers

                ck = get_shared_breakers()
                activate = getattr(ck, "activate_breaker", None)
                if activate is None:
                    pass
                elif inspect.iscoroutinefunction(activate):
                    try:
                        loop = asyncio.get_running_loop()
                    except RuntimeError:
                        loop = None
                    if loop is None:
                        asyncio.run(activate("system_integrity", BREAKER_REASON_IC2))
                    else:
                        logger.debug(
                            "[IC-2] breaker async diferido (loop activo) — "
                            "caller debe sync"
                        )
                else:
                    activate("system_integrity", BREAKER_REASON_IC2)
            except Exception as exc:  # noqa: BLE001
                logger.debug("[IC-2] breaker sync skip: %s", exc)

        self.state.armed = False
        # flatten_pending permanece True → mark_to_market / ciclo liquida inventario
        logger.error(
            "[IC-2] book Core desarmado (flatten_pending=%s) — "
            "no re-armar sin diagnóstico (≥30 min runbook)",
            self.state.flatten_pending,
        )

    def flatten_core_paper(
        self,
        *,
        positions: Mapping[str, Decimal],
        marks: Mapping[str, Any],
        sell: FlattenPort,
    ) -> List[Any]:
        """Liquida inventario paper del Core vía `sell` inyectado (Decimal)."""
        fills: List[Any] = []
        for symbol, qty in positions.items():
            qty_d = _to_decimal(qty, f"qty[{symbol}]")
            if qty_d <= ZERO:
                continue
            if symbol not in marks:
                raise InventoryControlInputError(
                    f"falta mark para flatten {symbol}"
                )
            px = _to_decimal(marks[symbol], f"mark[{symbol}]")
            fills.append(sell(symbol=symbol, quantity=qty_d, price=px))
        self.state.ic2_active = True
        self.state.armed = False
        self.state.flatten_pending = False
        self.state.last_events.append(
            _event(EVENT_IC2, flattened=True, symbols=list(positions.keys()))
        )
        _publish_metrics(self.state)
        return fills

    def rearm(self, *, reason: str) -> None:
        """Re-arm manual tras diagnóstico escrito (desk §5.3 / L0 §2.2)."""
        if not reason or not str(reason).strip():
            raise InventoryControlInputError("rearm exige reason escrita")
        self.state.armed = True
        self.state.ic2_active = False
        self.state.flatten_pending = False
        self.state.last_events.append(
            _event("IC2_rearm", reason=str(reason).strip())
        )
        logger.warning("[IC-2] re-arm: %s", reason)
        _publish_metrics(self.state)


_shared_guard: Optional[InventoryControlGuard] = None


def get_inventory_control_guard() -> InventoryControlGuard:
    global _shared_guard
    if _shared_guard is None:
        _shared_guard = InventoryControlGuard()
    return _shared_guard


def reset_inventory_control_guard(
    config: Optional[IcControlsConfig] = None,
) -> InventoryControlGuard:
    """Solo tests / reinicio paper controlado."""
    global _shared_guard
    _shared_guard = InventoryControlGuard(config=config)
    return _shared_guard


def evaluate_and_enforce_from_paper(
    *,
    mid: Any,
    equity_mtm: Any,
    peak_equity: Optional[Any] = None,
    range_floor: Optional[Any] = None,
    enforce: bool = True,
    guard: Optional[InventoryControlGuard] = None,
) -> InventoryControlDecision:
    """Punto de enganche del ciclo paper / mark_to_market."""
    g = guard or get_inventory_control_guard()
    return g.observe(
        mid=mid,
        equity_mtm=equity_mtm,
        peak_equity=peak_equity,
        range_floor=range_floor,
        enforce=enforce,
    )


def maybe_flatten_open_inventory_paper(
    *,
    positions: Mapping[str, Decimal],
    marks: Mapping[str, Any],
    sell: FlattenPort,
    guard: Optional[InventoryControlGuard] = None,
) -> List[Any]:
    """IC-B: si flatten_pending, liquida inventario paper vía ``sell`` (ledger)."""
    g = guard or get_inventory_control_guard()
    if not g.state.flatten_pending:
        return []
    open_pos = {
        str(sym).upper(): qty
        for sym, qty in positions.items()
        if _to_decimal(qty, f"qty[{sym}]") > ZERO
    }
    if not open_pos:
        g.state.flatten_pending = False
        return []
    return g.flatten_core_paper(positions=open_pos, marks=marks, sell=sell)
