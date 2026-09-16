"""Ledger de equity paper — fuente de verdad de la telemetría del tear sheet (S10).

Este módulo es la **única fuente de verdad** del estado paper del bot. Los tres
simuladores históricos quedan deprecados a su favor (gap I-4 de
`Docs/engineering/tear-sheet-spec.md` §6.1):

| Camino histórico | Estado |
|---|---|
| `BinanceService._simulate_order()` | deprecado: devuelve una orden FILLED sin efecto contable |
| `PaperTradingSystem` (`paper_trading_state.json`) | deprecado: floats y sin fees ni slippage |
| `OptimizedGridManager._place_order()` (rama paper) | calcula la comisión y la descarta |

Qué resuelve, con la nomenclatura de gaps del spec:

- **I-3 / I-7** El equity se marca a ticker real. No hay precios constantes: si el
  feed no responde, `MarkPriceUnavailable` — nunca un número inventado.
- **I-5 / I-6** Comisión (10 bps/lado maker) y selección adversa (2 bps/lado) se
  **restan del cash**: 24 bps round-trip.
- **I-8** `cycle_id` empareja la compra de un nivel con su venta. Bloqueante para
  contar los ≥120 ciclos cerrados de `Docs/squad/desk-policy-l0.md` §3.2.
- **I-12** `config_hash` viaja en cada marca de equity (gate A1: freeze de config).
- **I-13** Cierre diario anclado a 00:00 UTC: de ahí sale la serie `r_t`.

Invariante contable central (gate A4, con tolerancia cero por construcción):

```
E_T − E_0 = pnl_neto_realizado + pnl_no_realizado
```

Todo el dinero es `Decimal` y los `float` se rechazan con `TypeError`
(regla `10-financial-integrity`). La conversión desde el ticker ocurre en el
borde del sistema, explícitamente.

**Paper-only.** Este módulo no envía órdenes ni toca flags de trading.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Protocol, Set, Tuple

from app.core.primary_symbol import resolve_primary_symbol

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1

# Modelo de costos de `tear-sheet-spec.md` §4.4, adoptado por el desk en §2.1.
DEFAULT_MAKER_FEE_BPS = Decimal("10")
DEFAULT_TAKER_FEE_BPS = Decimal("10")
DEFAULT_ADVERSE_SELECTION_BPS = Decimal("2")

BPS = Decimal("10000")
ZERO = Decimal("0")

# Ventana de tolerancia para considerar un snapshot como cierre diario 00:00 UTC.
# El agente de snapshots corre cada 900 s, así que 30 min garantizan una marca.
DAILY_CLOSE_TOLERANCE = timedelta(minutes=30)

# Claves que nunca entran al `config_hash` (regla 40 / 10-financial-integrity).
SECRET_KEY_HINTS = (
    "key",
    "secret",
    "token",
    "password",
    "passwd",
    "credential",
    "webhook",
)

QUOTE_ASSETS = ("USDT", "USDC", "BUSD", "FDUSD")


class PaperLedgerError(Exception):
    """Error base de la telemetría paper."""


# G18/G19: lock distribuido de la serie JSON (RCA-G18-G19-series.md).
# TTL corto anti-deadlock si un worker muere. No file-lock. PROMOTE_LIVE: NO.
SERIES_LOCK_KEY = "lock:paper:equity_series"
SERIES_LOCK_TTL_SECONDS = 5
SERIES_LOCK_BLOCKING_TIMEOUT_SECONDS = 10


def _paper_series_lock_enabled() -> bool:
    raw = os.getenv("PAPER_EQUITY_SERIES_LOCK", "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


class MarkPriceUnavailable(PaperLedgerError):
    """No hay precio de marcación real. Falla cerrado: no se inventa un precio."""


class InsufficientPaperBalance(PaperLedgerError):
    """El cash paper no cubre notional + fee + slippage."""


class InsufficientPaperInventory(PaperLedgerError):
    """Se intentó vender más inventario del que el ledger tiene abierto."""


class PaperDeployedCapitalExceeded(PaperLedgerError):
    """El notional de inventario paper superaría `deployed_capital` (mandato L0-A)."""


# ---------------------------------------------------------------------------
# Utilidades de dinero — Decimal obligatorio
# ---------------------------------------------------------------------------


def _normalize(value: Decimal) -> Decimal:
    """Quita ceros de cola sin introducir notación científica ni redondear."""
    normalized = value.normalize()
    exponent = normalized.as_tuple().exponent
    if isinstance(exponent, int) and exponent > 0:
        normalized = normalized.quantize(Decimal(1))
    return normalized


def to_money(value: Any, *, field_name: str = "monto") -> Decimal:
    """Convierte a `Decimal` rechazando `float`.

    El `float` no se acepta ni por conveniencia: un `0.1` binario en un ledger
    contable es una pérdida silenciosa. La conversión desde datos externos
    (tickers, JSON del exchange) se hace con `str(...)` en el borde.
    """
    if isinstance(value, Decimal):
        return _normalize(value)
    if isinstance(value, bool) or isinstance(value, float):
        raise TypeError(
            f"{field_name} debe ser Decimal/str/int, no {type(value).__name__} "
            "(regla 10-financial-integrity)"
        )
    if isinstance(value, (int, str)):
        return _normalize(Decimal(value))
    raise TypeError(f"{field_name} no convertible a Decimal: {type(value).__name__}")


def _money_str(value: Decimal) -> str:
    return str(_normalize(value))


def _as_utc(moment: datetime) -> datetime:
    """Un timestamp sin tz se interpreta como UTC: la ventana es UTC por spec."""
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def _base_asset(symbol: str) -> str:
    upper = symbol.upper()
    for quote in QUOTE_ASSETS:
        if upper.endswith(quote) and len(upper) > len(quote):
            return upper[: -len(quote)]
    return upper


# ---------------------------------------------------------------------------
# I-12 — config_hash
# ---------------------------------------------------------------------------


def _strip_secrets(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            k: _strip_secrets(v)
            for k, v in value.items()
            if not any(hint in str(k).lower() for hint in SECRET_KEY_HINTS)
        }
    if isinstance(value, (list, tuple)):
        return [_strip_secrets(v) for v in value]
    if isinstance(value, Decimal):
        return _money_str(value)
    return value


def compute_config_hash(config: Mapping[str, Any]) -> str:
    """Hash sha256 estable de la config del grid, sin secrets (gate A1).

    Determinista e independiente del orden de las claves: sirve para probar que
    la config no se movió dentro de la ventana. Cualquier cambio de spacing,
    niveles, sizing o símbolo produce otro hash y dispara N11.
    """
    canonical = json.dumps(
        _strip_secrets(config), sort_keys=True, separators=(",", ":"), default=str
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


DEFAULT_GRID_CONFIG_FILE = "grid_config_optimized.json"


def resolve_expected_config_hash() -> Optional[str]:
    """Expected A1: `GRID_CONFIG_HASH` o sidecar `<stem>.hash` junto al JSON."""
    explicit = (os.getenv("GRID_CONFIG_HASH") or "").strip()
    if explicit:
        return explicit
    cfg_path = Path(os.getenv("GRID_CONFIG_FILE", "grid_config_paper_l0.json"))
    sidecar = cfg_path.with_name(f"{cfg_path.stem}.hash")
    try:
        text = sidecar.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return text or None


def resolve_grid_config_hash() -> Optional[str]:
    """`config_hash` de la config de grid vigente, para el freeze de la ventana.

    Orden de resolución: `GRID_CONFIG_HASH` explícito (lo que el desk congela en
    `Docs/squad/desk-policy-l0.md` §6 C3) y, si no está, el hash del archivo de
    config que efectivamente carga el bot. Devuelve `None` si no hay config
    legible: es preferible una serie sin hash —y por lo tanto un gate A1 que no se
    puede firmar— a un hash inventado que dé por congelado algo que no lo está.
    """
    explicit = os.getenv("GRID_CONFIG_HASH")
    if explicit:
        return explicit
    path = Path(os.getenv("GRID_CONFIG_FILE", DEFAULT_GRID_CONFIG_FILE))
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning(
            "[PaperLedger] Sin config_hash: %s no es legible (%s). El gate A1 no se "
            "puede probar hasta que el desk congele GRID_CONFIG_HASH",
            path,
            exc,
        )
        return None
    if not isinstance(config, Mapping):
        return None
    return compute_config_hash(config)


# ---------------------------------------------------------------------------
# Modelo de costos
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PaperCostModel:
    """24 bps round-trip: 10 bps de fee maker + 2 bps de selección adversa, por lado.

    La selección adversa es un **supuesto declarado** (Anexo B.2 del spec), no una
    medición: los limits del grid se llenan preferentemente cuando el precio sigue
    moviéndose en contra. Debe recalibrarse contra fills reales.
    """

    maker_fee_bps: Decimal = DEFAULT_MAKER_FEE_BPS
    taker_fee_bps: Decimal = DEFAULT_TAKER_FEE_BPS
    adverse_selection_bps: Decimal = DEFAULT_ADVERSE_SELECTION_BPS

    def __post_init__(self) -> None:
        for name in ("maker_fee_bps", "taker_fee_bps", "adverse_selection_bps"):
            value = to_money(getattr(self, name), field_name=name)
            if value < ZERO:
                raise ValueError(f"{name} no puede ser negativo: {value}")
            object.__setattr__(self, name, value)

    def fee_bps(self, order_type: str = "LIMIT") -> Decimal:
        return self.taker_fee_bps if str(order_type).upper() == "MARKET" else self.maker_fee_bps

    def cost_bps_per_side(self, order_type: str = "LIMIT") -> Decimal:
        return self.fee_bps(order_type) + self.adverse_selection_bps

    @property
    def round_trip_bps(self) -> Decimal:
        return self.cost_bps_per_side("LIMIT") * 2

    def fee_usdt(self, notional: Decimal, order_type: str = "LIMIT") -> Decimal:
        return _normalize(notional * self.fee_bps(order_type) / BPS)

    def slippage_usdt(self, notional: Decimal) -> Decimal:
        return _normalize(notional * self.adverse_selection_bps / BPS)

    def to_dict(self) -> Dict[str, str]:
        return {
            "maker_fee_bps": _money_str(self.maker_fee_bps),
            "taker_fee_bps": _money_str(self.taker_fee_bps),
            "adverse_selection_bps": _money_str(self.adverse_selection_bps),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "PaperCostModel":
        return cls(
            maker_fee_bps=to_money(payload["maker_fee_bps"]),
            taker_fee_bps=to_money(payload["taker_fee_bps"]),
            adverse_selection_bps=to_money(payload["adverse_selection_bps"]),
        )


# ---------------------------------------------------------------------------
# Fills y ciclos de grid
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PaperFill:
    """Fill paper con fee atribuida (gate A5) — persiste en el JSON del ledger."""

    fill_id: str
    cycle_id: str
    symbol: str
    side: str
    quantity: Decimal
    price: Decimal
    order_type: str
    notional_usdt: Decimal
    commission: Decimal
    commission_asset: str
    commission_usdt: Decimal
    slippage_usdt: Decimal
    grid_level: Optional[int]
    executed_at: datetime
    cycle_ids: Tuple[str, ...] = ()
    client_order_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fill_id": self.fill_id,
            "cycle_id": self.cycle_id,
            "cycle_ids": list(self.cycle_ids),
            "symbol": self.symbol,
            "side": self.side,
            "quantity": _money_str(self.quantity),
            "price": _money_str(self.price),
            "order_type": self.order_type,
            "notional_usdt": _money_str(self.notional_usdt),
            "commission": _money_str(self.commission),
            "commission_asset": self.commission_asset,
            "commission_usdt": _money_str(self.commission_usdt),
            "slippage_usdt": _money_str(self.slippage_usdt),
            "grid_level": self.grid_level,
            "executed_at": self.executed_at.isoformat(),
            "client_order_id": self.client_order_id,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "PaperFill":
        return cls(
            fill_id=payload["fill_id"],
            cycle_id=payload["cycle_id"],
            cycle_ids=tuple(payload.get("cycle_ids") or ()),
            symbol=payload["symbol"],
            side=payload["side"],
            quantity=to_money(payload["quantity"]),
            price=to_money(payload["price"]),
            order_type=payload["order_type"],
            notional_usdt=to_money(payload["notional_usdt"]),
            commission=to_money(payload["commission"]),
            commission_asset=payload["commission_asset"],
            commission_usdt=to_money(payload["commission_usdt"]),
            slippage_usdt=to_money(payload["slippage_usdt"]),
            grid_level=payload.get("grid_level"),
            executed_at=_as_utc(datetime.fromisoformat(payload["executed_at"])),
            client_order_id=str(payload.get("client_order_id") or ""),
        )


@dataclass
class GridCycle:
    """Round-trip de un nivel del grid: la compra y la venta que la cierra (I-8).

    Un ciclo cuenta como cerrado sólo cuando `open_quantity` llega a cero. La
    contabilidad de costos se lleva por remanentes (no por prorrateo repetido)
    para que la suma de las asignaciones sea exacta y la identidad A4 cierre sin
    tolerancia.
    """

    cycle_id: str
    symbol: str
    grid_level: Optional[int]
    buy_price: Decimal
    buy_quantity: Decimal
    open_quantity: Decimal
    buy_fee_usdt: Decimal
    buy_slippage_usdt: Decimal
    buy_fee_remaining: Decimal
    buy_slippage_remaining: Decimal
    opened_at: datetime
    closed_quantity: Decimal = ZERO
    sell_notional_usdt: Decimal = ZERO
    gross_pnl_usdt: Decimal = ZERO
    net_pnl_usdt: Decimal = ZERO
    fees_usdt: Decimal = ZERO
    slippage_usdt: Decimal = ZERO
    closed_at: Optional[datetime] = None

    @property
    def state(self) -> str:
        return "closed" if self.open_quantity == ZERO else "open"

    @property
    def cost_basis_open(self) -> Decimal:
        """Costo del inventario abierto, fees y slippage de compra incluidos."""
        return _normalize(
            self.buy_price * self.open_quantity
            + self.buy_fee_remaining
            + self.buy_slippage_remaining
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "symbol": self.symbol,
            "grid_level": self.grid_level,
            "state": self.state,
            "buy_price": _money_str(self.buy_price),
            "buy_quantity": _money_str(self.buy_quantity),
            "open_quantity": _money_str(self.open_quantity),
            "buy_fee_usdt": _money_str(self.buy_fee_usdt),
            "buy_slippage_usdt": _money_str(self.buy_slippage_usdt),
            "buy_fee_remaining": _money_str(self.buy_fee_remaining),
            "buy_slippage_remaining": _money_str(self.buy_slippage_remaining),
            "closed_quantity": _money_str(self.closed_quantity),
            "sell_notional_usdt": _money_str(self.sell_notional_usdt),
            "gross_pnl_usdt": _money_str(self.gross_pnl_usdt),
            "net_pnl_usdt": _money_str(self.net_pnl_usdt),
            "fees_usdt": _money_str(self.fees_usdt),
            "slippage_usdt": _money_str(self.slippage_usdt),
            "opened_at": self.opened_at.isoformat(),
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "GridCycle":
        closed_at = payload.get("closed_at")
        return cls(
            cycle_id=payload["cycle_id"],
            symbol=payload["symbol"],
            grid_level=payload.get("grid_level"),
            buy_price=to_money(payload["buy_price"]),
            buy_quantity=to_money(payload["buy_quantity"]),
            open_quantity=to_money(payload["open_quantity"]),
            buy_fee_usdt=to_money(payload["buy_fee_usdt"]),
            buy_slippage_usdt=to_money(payload["buy_slippage_usdt"]),
            buy_fee_remaining=to_money(payload["buy_fee_remaining"]),
            buy_slippage_remaining=to_money(payload["buy_slippage_remaining"]),
            closed_quantity=to_money(payload["closed_quantity"]),
            sell_notional_usdt=to_money(payload["sell_notional_usdt"]),
            gross_pnl_usdt=to_money(payload["gross_pnl_usdt"]),
            net_pnl_usdt=to_money(payload["net_pnl_usdt"]),
            fees_usdt=to_money(payload["fees_usdt"]),
            slippage_usdt=to_money(payload["slippage_usdt"]),
            opened_at=_as_utc(datetime.fromisoformat(payload["opened_at"])),
            closed_at=_as_utc(datetime.fromisoformat(closed_at)) if closed_at else None,
        )


# ---------------------------------------------------------------------------
# Ledger
# ---------------------------------------------------------------------------


def _default_deployed_capital() -> Decimal:
    """Capital desplegado del tramo L0-A (desk-policy-l0 §2.3): USD 200."""
    return to_money(
        os.getenv("PAPER_DEPLOYED_CAPITAL_USDT", "200"),
        field_name="PAPER_DEPLOYED_CAPITAL_USDT",
    )


class PaperEquityLedger:
    """Cash + inventario paper con costos aplicados y ciclos de grid emparejados."""

    def __init__(
        self,
        initial_cash: Any = "1000",
        *,
        deployed_capital: Any = None,
        cost_model: Optional[PaperCostModel] = None,
        quote_asset: str = "USDT",
        storage_path: Optional[Path] = None,
    ) -> None:
        self._initial_cash = to_money(initial_cash, field_name="initial_cash")
        self._cash = self._initial_cash
        self._deployed_capital = (
            to_money(deployed_capital, field_name="deployed_capital")
            if deployed_capital is not None
            else _default_deployed_capital()
        )
        self.cost_model = cost_model or PaperCostModel()
        self.quote_asset = quote_asset.upper()
        self.storage_path = Path(storage_path) if storage_path else None
        self._cycles: List[GridCycle] = []
        self._fills: List[PaperFill] = []
        self._realized_gross = ZERO
        self._realized_net = ZERO
        self._fees_total = ZERO
        self._slippage_total = ZERO
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = self.created_at

    # -- lectura ------------------------------------------------------------

    @property
    def cash(self) -> Decimal:
        return self._cash

    @property
    def initial_cash(self) -> Decimal:
        return self._initial_cash

    @property
    def deployed_capital(self) -> Decimal:
        """Tope de notional de inventario paper y denominador MaxDD (L0-A / desk §3.3)."""
        return self._deployed_capital

    def open_inventory_notional(self) -> Decimal:
        """Notional abierto Σ qty × buy_price (sin fees). Gate vs `deployed_capital`."""
        return _normalize(
            sum((c.buy_price * c.open_quantity for c in self.open_cycles()), ZERO)
        )

    @property
    def fills(self) -> Tuple[PaperFill, ...]:
        return tuple(self._fills)

    @property
    def cycles(self) -> Tuple[GridCycle, ...]:
        return tuple(self._cycles)

    @property
    def fees_total_usdt(self) -> Decimal:
        return self._fees_total

    @property
    def slippage_total_usdt(self) -> Decimal:
        return self._slippage_total

    @property
    def realized_gross_pnl_usdt(self) -> Decimal:
        return self._realized_gross

    @property
    def realized_net_pnl_usdt(self) -> Decimal:
        return self._realized_net

    @property
    def closed_cycle_count(self) -> int:
        return sum(1 for cycle in self._cycles if cycle.state == "closed")

    @property
    def open_cycle_count(self) -> int:
        return sum(1 for cycle in self._cycles if cycle.state == "open")

    def closed_cycles(self) -> List[GridCycle]:
        return [cycle for cycle in self._cycles if cycle.state == "closed"]

    def open_cycles(self, symbol: Optional[str] = None) -> List[GridCycle]:
        upper = symbol.upper() if symbol else None
        return [
            cycle
            for cycle in self._cycles
            if cycle.state == "open" and (upper is None or cycle.symbol == upper)
        ]

    def position(self, symbol: str) -> Decimal:
        return _normalize(
            sum((c.open_quantity for c in self.open_cycles(symbol)), ZERO)
        )

    def symbols(self) -> List[str]:
        seen: List[str] = []
        for cycle in self.open_cycles():
            if cycle.symbol not in seen:
                seen.append(cycle.symbol)
        return seen

    # -- escritura ----------------------------------------------------------

    def record_buy(
        self,
        symbol: str,
        quantity: Any,
        price: Any,
        *,
        order_type: str = "LIMIT",
        grid_level: Optional[int] = None,
        executed_at: Optional[datetime] = None,
        cycle_id: Optional[str] = None,
        client_order_id: Optional[str] = None,
    ) -> PaperFill:
        """Abre un ciclo de grid y descuenta notional + fee + slippage del cash.

        Gate L0-A: el notional de inventario abierto + el de esta compra no puede
        superar `deployed_capital` (paper; no toca live).
        """
        symbol = symbol.upper()
        qty = to_money(quantity, field_name="quantity")
        px = to_money(price, field_name="price")
        if qty <= ZERO or px <= ZERO:
            raise ValueError("quantity y price deben ser positivos")

        notional = _normalize(qty * px)
        projected = _normalize(self.open_inventory_notional() + notional)
        if projected > self._deployed_capital:
            raise PaperDeployedCapitalExceeded(
                f"inventario paper {self.open_inventory_notional()} + notional "
                f"{notional} = {projected} supera deployed_capital "
                f"{self._deployed_capital}"
            )
        fee = self.cost_model.fee_usdt(notional, order_type)
        slippage = self.cost_model.slippage_usdt(notional)
        total = _normalize(notional + fee + slippage)
        if total > self._cash:
            raise InsufficientPaperBalance(
                f"cash paper {self._cash} < {total} requeridos para {symbol}"
            )

        moment = _as_utc(executed_at or datetime.now(timezone.utc))
        cycle = GridCycle(
            cycle_id=cycle_id or f"cyc-{uuid.uuid4().hex[:12]}",
            symbol=symbol,
            grid_level=grid_level,
            buy_price=px,
            buy_quantity=qty,
            open_quantity=qty,
            buy_fee_usdt=fee,
            buy_slippage_usdt=slippage,
            buy_fee_remaining=fee,
            buy_slippage_remaining=slippage,
            opened_at=moment,
        )
        self._cycles.append(cycle)
        self._cash = _normalize(self._cash - total)
        self._fees_total = _normalize(self._fees_total + fee)
        self._slippage_total = _normalize(self._slippage_total + slippage)

        cid = str(client_order_id or "").strip()
        if client_order_id is not None and not cid:
            raise ValueError("client_order_id no puede estar vacío")
        if not cid:
            cid = f"paper-{uuid.uuid4().hex[:16]}"
        fill = PaperFill(
            fill_id=f"fil-{uuid.uuid4().hex[:12]}",
            cycle_id=cycle.cycle_id,
            cycle_ids=(cycle.cycle_id,),
            symbol=symbol,
            side="BUY",
            quantity=qty,
            price=px,
            order_type=order_type.upper(),
            notional_usdt=notional,
            commission=fee,
            commission_asset=self.quote_asset,
            commission_usdt=fee,
            slippage_usdt=slippage,
            grid_level=grid_level,
            executed_at=moment,
            client_order_id=cid,
        )
        self._append_fill(fill)
        return fill

    def record_sell(
        self,
        symbol: str,
        quantity: Any,
        price: Any,
        *,
        order_type: str = "LIMIT",
        executed_at: Optional[datetime] = None,
        client_order_id: Optional[str] = None,
    ) -> PaperFill:
        """Cierra ciclos FIFO, acredita el neto y cuenta los round-trips completos."""
        symbol = symbol.upper()
        qty = to_money(quantity, field_name="quantity")
        px = to_money(price, field_name="price")
        if qty <= ZERO or px <= ZERO:
            raise ValueError("quantity y price deben ser positivos")

        available = self.position(symbol)
        if qty > available:
            raise InsufficientPaperInventory(
                f"venta de {qty} {symbol} con inventario abierto {available}"
            )

        notional = _normalize(qty * px)
        fee_total = self.cost_model.fee_usdt(notional, order_type)
        slippage_total = self.cost_model.slippage_usdt(notional)
        moment = _as_utc(executed_at or datetime.now(timezone.utc))

        # Asignación FIFO por remanentes: la última tramo absorbe el residuo para
        # que Σ asignaciones == total exacto y la identidad A4 cierre sin drift.
        allocations: List[Tuple[GridCycle, Decimal]] = []
        remaining = qty
        for cycle in self.open_cycles(symbol):
            if remaining <= ZERO:
                break
            take = min(remaining, cycle.open_quantity)
            allocations.append((cycle, take))
            remaining = _normalize(remaining - take)

        fee_left = fee_total
        slip_left = slippage_total
        matched_ids: List[str] = []
        for index, (cycle, alloc) in enumerate(allocations):
            is_last = index == len(allocations) - 1
            if is_last:
                sell_fee = fee_left
                sell_slip = slip_left
            else:
                sell_fee = _normalize(fee_total * alloc / qty)
                sell_slip = _normalize(slippage_total * alloc / qty)
            fee_left = _normalize(fee_left - sell_fee)
            slip_left = _normalize(slip_left - sell_slip)

            if alloc == cycle.open_quantity:
                buy_fee = cycle.buy_fee_remaining
                buy_slip = cycle.buy_slippage_remaining
            else:
                frac = alloc / cycle.open_quantity
                buy_fee = _normalize(cycle.buy_fee_remaining * frac)
                buy_slip = _normalize(cycle.buy_slippage_remaining * frac)

            gross = _normalize((px - cycle.buy_price) * alloc)
            net = _normalize(gross - buy_fee - buy_slip - sell_fee - sell_slip)

            cycle.buy_fee_remaining = _normalize(cycle.buy_fee_remaining - buy_fee)
            cycle.buy_slippage_remaining = _normalize(
                cycle.buy_slippage_remaining - buy_slip
            )
            cycle.open_quantity = _normalize(cycle.open_quantity - alloc)
            cycle.closed_quantity = _normalize(cycle.closed_quantity + alloc)
            cycle.sell_notional_usdt = _normalize(
                cycle.sell_notional_usdt + px * alloc
            )
            cycle.gross_pnl_usdt = _normalize(cycle.gross_pnl_usdt + gross)
            cycle.net_pnl_usdt = _normalize(cycle.net_pnl_usdt + net)
            cycle.fees_usdt = _normalize(cycle.fees_usdt + buy_fee + sell_fee)
            cycle.slippage_usdt = _normalize(cycle.slippage_usdt + buy_slip + sell_slip)
            if cycle.open_quantity == ZERO:
                cycle.closed_at = moment

            self._realized_gross = _normalize(self._realized_gross + gross)
            self._realized_net = _normalize(self._realized_net + net)
            matched_ids.append(cycle.cycle_id)

        self._cash = _normalize(self._cash + notional - fee_total - slippage_total)
        self._fees_total = _normalize(self._fees_total + fee_total)
        self._slippage_total = _normalize(self._slippage_total + slippage_total)

        cid = str(client_order_id or "").strip()
        if client_order_id is not None and not cid:
            raise ValueError("client_order_id no puede estar vacío")
        if not cid:
            cid = f"paper-{uuid.uuid4().hex[:16]}"
        fill = PaperFill(
            fill_id=f"fil-{uuid.uuid4().hex[:12]}",
            cycle_id=matched_ids[0] if matched_ids else "",
            cycle_ids=tuple(matched_ids),
            symbol=symbol,
            side="SELL",
            quantity=qty,
            price=px,
            order_type=order_type.upper(),
            notional_usdt=notional,
            commission=fee_total,
            commission_asset=self.quote_asset,
            commission_usdt=fee_total,
            slippage_usdt=slippage_total,
            grid_level=None,
            executed_at=moment,
            client_order_id=cid,
        )
        self._append_fill(fill)
        return fill

    def _append_fill(self, fill: PaperFill) -> None:
        self._fills.append(fill)
        self.updated_at = fill.executed_at
        self._autosave()

    # -- marcación a mercado ------------------------------------------------

    def _marks(self, prices: Mapping[str, Any]) -> Dict[str, Decimal]:
        return {
            symbol.upper(): to_money(price, field_name=f"mark[{symbol}]")
            for symbol, price in prices.items()
        }

    def mark_to_market(self, prices: Mapping[str, Any]) -> Decimal:
        """`E_t = cash + Σ_a qty_a × mid_a`, con fees ya restadas del cash."""
        return self.equity_breakdown(prices)["equity"]

    def equity_breakdown(self, prices: Mapping[str, Any]) -> Dict[str, Any]:
        marks = self._marks(prices)
        positions: Dict[str, Dict[str, Decimal]] = {}
        inventory_value = ZERO
        for symbol in self.symbols():
            quantity = self.position(symbol)
            if symbol not in marks:
                raise MarkPriceUnavailable(
                    f"falta precio de marcación para {symbol}: el equity paper no se "
                    "calcula con precios inventados (gate A6)"
                )
            value = _normalize(quantity * marks[symbol])
            inventory_value = _normalize(inventory_value + value)
            positions[symbol] = {
                "quantity": quantity,
                "mark": marks[symbol],
                "value": value,
            }
        return {
            "cash": self._cash,
            "inventory_value": inventory_value,
            "equity": _normalize(self._cash + inventory_value),
            "positions": positions,
            "deployed_capital": self._deployed_capital,
        }

    def unrealized_pnl_usdt(self, prices: Mapping[str, Any]) -> Decimal:
        """`Σ qty_abierta × mid − costo_base_abierto` (costo base con fees incluidas)."""
        marks = self._marks(prices)
        total = ZERO
        for cycle in self.open_cycles():
            if cycle.symbol not in marks:
                raise MarkPriceUnavailable(cycle.symbol)
            total = _normalize(
                total + cycle.open_quantity * marks[cycle.symbol] - cycle.cost_basis_open
            )
        return total

    def cost_ratio(self) -> Optional[Decimal]:
        """`(fees + slippage) / pnl_bruto_realizado` — gate B2, el más informativo."""
        if self._realized_gross <= ZERO:
            return None
        return _normalize(
            (self._fees_total + self._slippage_total) / self._realized_gross
        )

    def inventory_ratio(self, prices: Mapping[str, Any]) -> Optional[Decimal]:
        """`|Δ pnl_no_realizado| / pnl_bruto_realizado` — auditoría si > 80%.

        Mide qué fracción del spread capturado se convirtió en exposición
        direccional (desk-policy-l0 §3.1). `None` si todavía no hay bruto realizado.
        """
        if self._realized_gross <= ZERO:
            return None
        return _normalize(abs(self.unrealized_pnl_usdt(prices)) / self._realized_gross)

    def as_binance_balances(self) -> List[Dict[str, str]]:
        """Balances con la forma del payload de Binance, derivados del ledger."""
        balances = [
            {"asset": self.quote_asset, "free": _money_str(self._cash), "locked": "0"}
        ]
        for symbol in self.symbols():
            balances.append(
                {
                    "asset": _base_asset(symbol),
                    "free": _money_str(self.position(symbol)),
                    "locked": "0",
                }
            )
        return balances

    # -- persistencia JSON versionada (sin migraciones Alembic) -------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "quote_asset": self.quote_asset,
            "initial_cash": _money_str(self._initial_cash),
            "cash": _money_str(self._cash),
            "deployed_capital": _money_str(self._deployed_capital),
            "cost_model": self.cost_model.to_dict(),
            "realized_gross_pnl_usdt": _money_str(self._realized_gross),
            "realized_net_pnl_usdt": _money_str(self._realized_net),
            "fees_total_usdt": _money_str(self._fees_total),
            "slippage_total_usdt": _money_str(self._slippage_total),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "cycles": [cycle.to_dict() for cycle in self._cycles],
            "fills": [fill.to_dict() for fill in self._fills],
        }

    @classmethod
    def from_dict(
        cls, payload: Mapping[str, Any], *, storage_path: Optional[Path] = None
    ) -> "PaperEquityLedger":
        version = payload.get("schema_version")
        if version != SCHEMA_VERSION:
            raise PaperLedgerError(
                f"schema_version {version} incompatible (esperado {SCHEMA_VERSION})"
            )
        ledger = cls(
            initial_cash=payload["initial_cash"],
            deployed_capital=payload["deployed_capital"],
            cost_model=PaperCostModel.from_dict(payload["cost_model"]),
            quote_asset=payload.get("quote_asset", "USDT"),
            storage_path=storage_path,
        )
        ledger._cash = to_money(payload["cash"])
        ledger._realized_gross = to_money(payload["realized_gross_pnl_usdt"])
        ledger._realized_net = to_money(payload["realized_net_pnl_usdt"])
        ledger._fees_total = to_money(payload["fees_total_usdt"])
        ledger._slippage_total = to_money(payload["slippage_total_usdt"])
        ledger._cycles = [GridCycle.from_dict(c) for c in payload.get("cycles", [])]
        ledger._fills = [PaperFill.from_dict(f) for f in payload.get("fills", [])]
        ledger.created_at = _as_utc(datetime.fromisoformat(payload["created_at"]))
        ledger.updated_at = _as_utc(datetime.fromisoformat(payload["updated_at"]))
        return ledger

    def save(self, path: Optional[Path] = None) -> Path:
        destination = Path(path or self.storage_path or "")
        if not str(destination):
            raise PaperLedgerError("no hay path de persistencia para el ledger paper")
        _atomic_write_json(destination, self.to_dict())
        return destination

    @classmethod
    def load(
        cls, path: Path, *, storage_path: Optional[Path] = None
    ) -> "PaperEquityLedger":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(payload, storage_path=storage_path)

    def _autosave(self) -> None:
        if self.storage_path is None:
            return
        try:
            self.save()
        except Exception as exc:  # pragma: no cover - persistencia best-effort
            logger.error("[PaperLedger] No se pudo persistir el ledger paper: %s", exc)


# ---------------------------------------------------------------------------
# I-13 — serie de equity con cierre diario anclado a 00:00 UTC
# ---------------------------------------------------------------------------


def daily_close_anchor(
    moment: datetime, tolerance: timedelta = DAILY_CLOSE_TOLERANCE
) -> Optional[datetime]:
    """Medianoche UTC a la que pertenece el snapshot, o `None` si está lejos.

    Acepta marcas justo antes y justo después de las 00:00 para que el agente de
    snapshots (cada 900 s) siempre produzca un cierre diario.
    """
    moment = _as_utc(moment)
    midnight = moment.replace(hour=0, minute=0, second=0, microsecond=0)
    if moment - midnight <= tolerance:
        return midnight
    next_midnight = midnight + timedelta(days=1)
    if next_midnight - moment <= tolerance:
        return next_midnight
    return None


class PaperEquitySeries:
    """Serie de equity MtM: snapshots, cierres diarios, retornos y drawdown."""

    def __init__(
        self,
        *,
        config_hash: Optional[str] = None,
        deployed_capital: Any = None,
        storage_path: Optional[Path] = None,
    ) -> None:
        self.config_hash = config_hash
        self._deployed_capital = (
            to_money(deployed_capital, field_name="deployed_capital")
            if deployed_capital is not None
            else None
        )
        self.storage_path = Path(storage_path) if storage_path else None
        self._samples: List[Dict[str, Any]] = []

    @property
    def samples(self) -> List[Dict[str, Any]]:
        return list(self._samples)

    @property
    def deployed_capital(self) -> Optional[Decimal]:
        if self._deployed_capital is not None:
            return self._deployed_capital
        for sample in reversed(self._samples):
            if sample.get("deployed_capital"):
                return to_money(sample["deployed_capital"])
        return None

    def record(
        self,
        equity: Any,
        at: Optional[datetime] = None,
        *,
        cash: Any = None,
        inventory_value: Any = None,
        deployed_capital: Any = None,
        config_hash: Optional[str] = None,
    ) -> Dict[str, Any]:
        value = to_money(equity, field_name="equity")
        moment = _as_utc(at or datetime.now(timezone.utc))
        anchor = daily_close_anchor(moment)
        deployed = (
            to_money(deployed_capital, field_name="deployed_capital")
            if deployed_capital is not None
            else self._deployed_capital
        )
        sample = {
            "at": moment.isoformat(),
            "equity": _money_str(value),
            "cash": _money_str(to_money(cash)) if cash is not None else None,
            "inventory_value": (
                _money_str(to_money(inventory_value))
                if inventory_value is not None
                else None
            ),
            "deployed_capital": _money_str(deployed) if deployed is not None else None,
            "config_hash": config_hash or self.config_hash,
            "daily_close_at": anchor.isoformat() if anchor else None,
        }
        if self.storage_path is not None and _paper_series_lock_enabled():
            self._record_with_distributed_lock(sample)
        else:
            self._samples.append(sample)
            self._autosave()
        return sample

    # -- lecturas derivadas -------------------------------------------------

    def _sorted_samples(self) -> List[Dict[str, Any]]:
        return sorted(self._samples, key=lambda s: s["at"])

    def _equity_path(self) -> List[Tuple[datetime, Decimal]]:
        return [
            (_as_utc(datetime.fromisoformat(s["at"])), to_money(s["equity"]))
            for s in self._sorted_samples()
        ]

    def daily_closes(self) -> List[Tuple[datetime, Decimal]]:
        """Un cierre por día UTC: el snapshot más cercano a las 00:00."""
        best: Dict[str, Tuple[timedelta, Decimal]] = {}
        for sample in self._sorted_samples():
            anchor_iso = sample.get("daily_close_at")
            if not anchor_iso:
                continue
            anchor = _as_utc(datetime.fromisoformat(anchor_iso))
            moment = _as_utc(datetime.fromisoformat(sample["at"]))
            distance = abs(moment - anchor)
            current = best.get(anchor_iso)
            if current is None or distance < current[0]:
                best[anchor_iso] = (distance, to_money(sample["equity"]))
        return [
            (_as_utc(datetime.fromisoformat(iso)), equity)
            for iso, (_, equity) in sorted(best.items())
        ]

    def daily_returns(self) -> List[Decimal]:
        """`r_t = E_t / E_{t−1} − 1` sobre cierres diarios (frecuencia canónica)."""
        closes = self.daily_closes()
        returns: List[Decimal] = []
        for (_, previous), (_, current) in zip(closes, closes[1:]):
            if previous == ZERO:
                continue
            returns.append(_normalize(current / previous - 1))
        return returns

    def peak_equity_usdt(self) -> Optional[Decimal]:
        """Pico de equity MtM en la serie — insumo IC-2 (DD desde HWM del Core)."""
        path = self._equity_path()
        if not path:
            return None
        return max(eq for _, eq in path)

    def max_drawdown(self) -> Decimal:
        """`|min_t (E_t / max_{s≤t} E_s − 1)|` sobre toda la serie de snapshots."""
        peak = None
        worst = ZERO
        for _, equity in self._equity_path():
            if peak is None or equity > peak:
                peak = equity
            if peak and peak > ZERO:
                drawdown = _normalize(1 - equity / peak)
                if drawdown > worst:
                    worst = drawdown
        return worst

    def max_drawdown_usdt(self) -> Decimal:
        """Caída máxima en USD desde el pico previo. Insumo del umbral del desk."""
        peak = None
        worst = ZERO
        for _, equity in self._equity_path():
            if peak is None or equity > peak:
                peak = equity
            drop = _normalize(peak - equity)
            if drop > worst:
                worst = drop
        return worst

    def max_drawdown_pct_deployed(self, deployed_capital: Any = None) -> Optional[Decimal]:
        """MaxDD sobre **capital desplegado** — el número que gatea (desk §3.3).

        Medirlo contra el cap del book diluye el drawdown con cash ocioso: con 200
        desplegados de 560 asignados, el factor de dilución es 2,8×.
        """
        denominator = (
            to_money(deployed_capital, field_name="deployed_capital")
            if deployed_capital is not None
            else self.deployed_capital
        )
        if denominator is None or denominator <= ZERO:
            return None
        return _normalize(self.max_drawdown_usdt() / denominator)

    def config_hashes(self) -> Set[str]:
        hashes = {s["config_hash"] for s in self._samples if s.get("config_hash")}
        if self.config_hash:
            hashes.add(self.config_hash)
        return hashes

    def config_is_frozen(self, expected_hash: Optional[str] = None) -> bool:
        """Gate A1: exactamente un hash y debe coincidir con expected (fail-closed).

        Expected = argumento o ``resolve_expected_config_hash()`` (env/sidecar).
        Unicidad sola no basta (RCA sticky 2026-09-11).
        """
        hashes = {h for h in self.config_hashes() if h}
        if len(hashes) != 1:
            return False
        only = next(iter(hashes))
        expected = (
            expected_hash
            if expected_hash is not None
            else resolve_expected_config_hash()
        )
        if expected is None:
            return False
        return only == expected

    def coverage(self) -> Dict[str, Any]:
        """Insumo del gate A2: cantidad de marcas, gap máximo y cierres diarios."""
        path = self._equity_path()
        max_gap = 0
        for (previous, _), (current, _) in zip(path, path[1:]):
            max_gap = max(max_gap, int((current - previous).total_seconds()))
        return {
            "samples": len(path),
            "max_gap_seconds": max_gap,
            "daily_closes": len(self.daily_closes()),
            "first_at": path[0][0].isoformat() if path else None,
            "last_at": path[-1][0].isoformat() if path else None,
            "config_frozen": self.config_is_frozen(),
        }

    # -- persistencia -------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "config_hash": self.config_hash,
            "deployed_capital": (
                _money_str(self._deployed_capital)
                if self._deployed_capital is not None
                else None
            ),
            "samples": list(self._samples),
        }

    @classmethod
    def from_dict(
        cls, payload: Mapping[str, Any], *, storage_path: Optional[Path] = None
    ) -> "PaperEquitySeries":
        version = payload.get("schema_version")
        if version != SCHEMA_VERSION:
            raise PaperLedgerError(
                f"schema_version {version} incompatible (esperado {SCHEMA_VERSION})"
            )
        series = cls(
            config_hash=payload.get("config_hash"),
            deployed_capital=payload.get("deployed_capital"),
            storage_path=storage_path,
        )
        series._samples = list(payload.get("samples", []))
        return series

    def save(self, path: Optional[Path] = None) -> Path:
        destination = Path(path or self.storage_path or "")
        if not str(destination):
            raise PaperLedgerError("no hay path de persistencia para la serie paper")
        _atomic_write_json(destination, self.to_dict())
        return destination

    @classmethod
    def load(
        cls, path: Path, *, storage_path: Optional[Path] = None
    ) -> "PaperEquitySeries":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(payload, storage_path=storage_path)

    def _autosave(self) -> None:
        if self.storage_path is None:
            return
        try:
            self.save()
        except Exception as exc:  # pragma: no cover - persistencia best-effort
            logger.error("[PaperLedger] No se pudo persistir la serie paper: %s", exc)

    def _reload_samples_from_storage(self) -> None:
        if self.storage_path is None or not self.storage_path.exists():
            return
        loaded = type(self).load(self.storage_path, storage_path=self.storage_path)
        self._samples = list(loaded._samples)
        self.config_hash = loaded.config_hash
        self._deployed_capital = loaded._deployed_capital

    def _record_with_distributed_lock(self, sample: Dict[str, Any]) -> None:
        """Serializa reload+append+save entre workers. Fail-closed. TTL 5s.

        RCA G18/G19. No file-lock. PROMOTE_LIVE: NO.
        """
        from redis.exceptions import RedisError

        from app.core.distributed_lock import get_redis_client

        try:
            client = get_redis_client()
        except RedisError as exc:
            raise PaperLedgerError(f"series lock redis unavailable: {exc}") from exc

        lock = client.lock(
            SERIES_LOCK_KEY,
            timeout=SERIES_LOCK_TTL_SECONDS,
            blocking=True,
            blocking_timeout=SERIES_LOCK_BLOCKING_TIMEOUT_SECONDS,
        )
        try:
            acquired = lock.acquire(
                blocking=True,
                blocking_timeout=SERIES_LOCK_BLOCKING_TIMEOUT_SECONDS,
            )
        except RedisError as exc:
            raise PaperLedgerError(f"series lock redis unavailable: {exc}") from exc
        if not acquired:
            raise PaperLedgerError("series lock acquire timeout")
        try:
            self._reload_samples_from_storage()
            self._samples.append(sample)
            self.save()
        finally:
            try:
                lock.release()
            except RedisError as exc:
                logger.warning("[PaperLedger] No se pudo liberar series lock: %s", exc)


def _atomic_write_json(destination: Path, payload: Mapping[str, Any]) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    unique = f"{os.getpid()}.{uuid.uuid4().hex[:8]}"
    temporary = destination.with_name(f"{destination.name}.{unique}.tmp")
    try:
        temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(str(temporary), str(destination))
    except Exception:
        try:
            temporary.unlink()
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# I-7 — feed de precios de marcación (ticker real, nunca constantes)
# ---------------------------------------------------------------------------


class MarkPriceFeed(Protocol):
    def get_price(self, symbol: str) -> Decimal: ...


def mark_price_from_client(client: Any, symbol: str) -> Decimal:
    """Precio de marcación desde el ticker. `str()` en el borde, `Decimal` adentro."""
    if client is None:
        raise MarkPriceUnavailable(f"sin cliente de mercado para {symbol}")
    try:
        ticker = client.get_symbol_ticker(symbol=symbol.upper())
        price = to_money(str(ticker["price"]), field_name=f"ticker[{symbol}]")
    except MarkPriceUnavailable:
        raise
    except Exception as exc:
        raise MarkPriceUnavailable(f"ticker no disponible para {symbol}: {exc}") from exc
    if price <= ZERO:
        raise MarkPriceUnavailable(f"ticker devolvió precio no positivo para {symbol}")
    return price


class ClientMarkPriceFeed:
    """Feed sobre un cliente de exchange ya construido."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def get_price(self, symbol: str) -> Decimal:
        return mark_price_from_client(self._client, symbol)


class SingletonMarkPriceFeed:
    """Feed sobre el singleton de Binance. Endpoint público, sin credenciales."""

    def get_price(self, symbol: str) -> Decimal:
        from app.services.binance_client_singleton import get_binance_client_singleton

        return mark_price_from_client(get_binance_client_singleton().client, symbol)


def get_mark_price_feed() -> MarkPriceFeed:
    return SingletonMarkPriceFeed()


# ---------------------------------------------------------------------------
# Instancias de proceso y captura del snapshot paper
# ---------------------------------------------------------------------------


def _telemetry_dir() -> Path:
    from app.core.paths import get_writable_path

    return get_writable_path(os.getenv("PAPER_TELEMETRY_DIR", "paper_telemetry"))


_ledger: Optional[PaperEquityLedger] = None
_series: Optional[PaperEquitySeries] = None


def get_paper_ledger() -> PaperEquityLedger:
    """Ledger paper del proceso, rehidratado del JSON si existe."""
    global _ledger
    if _ledger is None:
        path = _telemetry_dir() / "paper_equity_ledger.json"
        if path.exists():
            try:
                _ledger = PaperEquityLedger.load(path, storage_path=path)
            except Exception as exc:
                logger.error(
                    "[PaperLedger] Ledger paper ilegible (%s); se arranca uno nuevo", exc
                )
        if _ledger is None:
            _ledger = PaperEquityLedger(
                initial_cash=os.getenv("PAPER_INITIAL_CASH_USDT", "1000"),
                storage_path=path,
            )
    return _ledger


def reload_paper_ledger_from_disk() -> PaperEquityLedger:
    """Rehidrata el singleton desde el JSON en disco.

    Celery prefork: ``execute_trading_cycle`` puede escribir el ledger en un
    child mientras ``trading_cycle_tick`` evalúa breakers en otro. Sin este
    reload, ``consecutive_losses_from_closed_cycles`` ve racha stale (0) y
    ``system_integrity`` no abre aunque el archivo ya tenga ≥5 pérdidas.
    Paper-only. PROMOTE_LIVE: NO.
    """
    global _ledger
    _ledger = None
    return get_paper_ledger()


def get_paper_equity_series() -> PaperEquitySeries:
    """Serie de equity paper del proceso, rehidratada del JSON si existe."""
    global _series
    if _series is None:
        path = _telemetry_dir() / "paper_equity_series.json"
        if path.exists():
            try:
                _series = PaperEquitySeries.load(path, storage_path=path)
            except Exception as exc:
                logger.error(
                    "[PaperLedger] Serie paper ilegible (%s); se arranca una nueva", exc
                )
        if _series is None:
            _series = PaperEquitySeries(
                config_hash=resolve_grid_config_hash(),
                storage_path=path,
            )
    return _series


def reset_paper_telemetry() -> None:
    """Descarta las instancias de proceso. Útil en tests y al reiniciar la ventana."""
    global _ledger, _series
    _ledger = None
    _series = None


def _apply_ic_wire_on_paper_snapshot(
    *,
    ledger: PaperEquityLedger,
    series: PaperEquitySeries,
    marks: Dict[str, Decimal],
    breakdown: Dict[str, Any],
) -> Dict[str, Any]:
    """IC-1/IC-2 en el path ticker real. Fail-soft: no rompe el snapshot.

    Si IC-2 flatten asienta SELL, recalcula el breakdown para que A3 cierre.
    Solo observa cuando el símbolo Core está en `marks` (el book IC es ETH L0);
    snapshots BTC-only de telemetría no disparan flatten.
    """
    if not marks:
        return breakdown
    try:
        from app.core.inventory_controls import (
            evaluate_and_enforce_from_paper,
            get_inventory_control_guard,
            maybe_flatten_open_inventory_paper,
        )

        guard = get_inventory_control_guard()
        core = str(guard.config.symbol or "").upper()
        if core and core not in marks:
            return breakdown

        mid = marks.get(core) or next(iter(marks.values()))
        equity = breakdown["equity"]
        peak = series.peak_equity_usdt()
        evaluate_and_enforce_from_paper(
            mid=mid,
            equity_mtm=equity,
            peak_equity=peak if peak is not None else equity,
            enforce=True,
            guard=guard,
        )
        if not guard.state.flatten_pending:
            return breakdown

        def _sell(*, symbol: str, quantity, price):
            return ledger.record_sell(
                symbol,
                quantity,
                price,
                order_type="MARKET",
            )

        positions = {sym: ledger.position(sym) for sym in ledger.symbols()}
        fills = maybe_flatten_open_inventory_paper(
            positions=positions,
            marks=marks,
            sell=_sell,
            guard=guard,
        )
        if fills:
            return ledger.equity_breakdown(marks)
    except Exception as ic_exc:  # noqa: BLE001 — marca no debe fallar por IC
        logger.warning("[PaperLedger] IC-WIRE observe skip: %s", ic_exc)
    return breakdown


def compute_paper_portfolio_value(
    *,
    ledger: Optional[PaperEquityLedger] = None,
    price_feed: Optional[MarkPriceFeed] = None,
    series: Optional[PaperEquitySeries] = None,
    at: Optional[datetime] = None,
    record: bool = True,
) -> Optional[Dict[str, Any]]:
    """Marca el ledger paper a ticker real y devuelve el payload de `portfolio_snapshots`.

    Devuelve `None` si falta algún precio de marcación: es preferible un hueco en
    la serie (detectable por el gate A2) a un equity fabricado (gate A6). Como
    efecto deseado, registra la marca en la serie de equity con su `config_hash` y
    su `deployed_capital`.

    Tras la marca, observa IC-1/IC-2 (path ops ticker real). Si IC-2 flatten
    asienta SELL, re-marca y graba la serie post-flatten (gate A3).

    Los `float` del payload existen sólo porque las columnas del ORM son `Float`
    (deuda técnica I-21); la contabilidad interna es íntegramente `Decimal`.
    """
    ledger = ledger if ledger is not None else get_paper_ledger()
    feed = price_feed if price_feed is not None else get_mark_price_feed()
    target_series = series if series is not None else get_paper_equity_series()

    marks: Dict[str, Decimal] = {}
    for symbol in ledger.symbols():
        try:
            marks[symbol] = feed.get_price(symbol)
        except MarkPriceUnavailable as exc:
            logger.error(
                "[PaperLedger] Snapshot paper omitido: sin precio de marcación (%s)", exc
            )
            return None

    breakdown = ledger.equity_breakdown(marks)
    if marks:
        breakdown = _apply_ic_wire_on_paper_snapshot(
            ledger=ledger,
            series=target_series,
            marks=marks,
            breakdown=breakdown,
        )

    btc_value = ZERO
    other_value = ZERO
    btc_price: Optional[Decimal] = None
    for symbol, position in breakdown["positions"].items():
        if _base_asset(symbol) == "BTC":
            btc_value = _normalize(btc_value + position["value"])
            btc_price = position["mark"]
        else:
            other_value = _normalize(other_value + position["value"])

    if record:
        # A1: no heredar header sticky (RCA gap126h/hash-drift 2026-09-11).
        target_series.record(
            breakdown["equity"],
            at=at,
            cash=breakdown["cash"],
            inventory_value=breakdown["inventory_value"],
            deployed_capital=ledger.deployed_capital,
            config_hash=resolve_grid_config_hash(),
        )
        # Persist ledger even without fills so fees/slippage/cost_model are on disk
        # for the first tick / Celery snapshot path (C3 E2E PaperEquityLedger).
        ledger._autosave()

    return {
        "total_value_usdt": float(breakdown["equity"]),
        "usdt_free": float(breakdown["cash"]),
        "btc_value_usdt": float(btc_value),
        "other_assets_usdt": float(other_value),
        "btc_price": float(btc_price) if btc_price is not None else None,
        "primary_symbol": resolve_primary_symbol(),
    }


def paper_equity_is_source_of_truth() -> bool:
    """`True` cuando el modo efectivo es paper: ahí el ledger manda sobre el exchange."""
    from app.core.trading_mode import get_trading_mode_snapshot

    return get_trading_mode_snapshot()["effective_mode"] == "paper"


__all__ = [
    "SCHEMA_VERSION",
    "DAILY_CLOSE_TOLERANCE",
    "ClientMarkPriceFeed",
    "GridCycle",
    "InsufficientPaperBalance",
    "InsufficientPaperInventory",
    "PaperDeployedCapitalExceeded",
    "MarkPriceFeed",
    "MarkPriceUnavailable",
    "PaperCostModel",
    "PaperEquityLedger",
    "PaperEquitySeries",
    "PaperFill",
    "PaperLedgerError",
    "SingletonMarkPriceFeed",
    "compute_config_hash",
    "compute_paper_portfolio_value",
    "daily_close_anchor",
    "resolve_expected_config_hash",
    "resolve_grid_config_hash",
    "get_mark_price_feed",
    "get_paper_equity_series",
    "get_paper_ledger",
    "mark_price_from_client",
    "paper_equity_is_source_of_truth",
    "reset_paper_telemetry",
    "SERIES_LOCK_KEY",
    "SERIES_LOCK_TTL_SECONDS",
    "to_money",
]
