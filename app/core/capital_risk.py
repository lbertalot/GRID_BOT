"""Capital risk engine — kill por drawdown + daily loss limit (ADR-003).

Política vigente (All Hands CEO 2026-08-05, RFC-002, y corrección del `RISK_BLOCK`
levantado por el Desk Lead en `Docs/squad/desk-policy-l0.md` §1.3):

- `contributed_capital` = capital aportado acumulado (hoy USD 1.000). **No HWM.**
- La reserva de ops sale del mismo pool, así que se calculan **dos bases**:
  - `dd_pool = (equity_trading + ops_remaining) / contributed_capital − 1`
    → lectura literal del CEO (KPI K3). **Informativa**: alerta, no kill.
  - `dd_trading = equity_trading / tradable_capital − 1`, con
    `tradable_capital = contributed_capital − ops_reserve_committed`
    → aísla el desempeño de la estrategia. **Gobierna el kill** por decisión del
    CEO (`KILL_BASIS=trading`, default).
- Sin esta separación, gastar la reserva de ops era indistinguible de perder el
  capital: con 250 de ops el kill disparaba con P&L de trading igual a cero.
- `kill_driven_by_ops_burn` marca justamente ese caso (rompe pool pero no trading).
- Daily loss `<= -DAILY_LOSS_LIMIT_PCT` vs equity EOD previo → flat 24 h.

Todo el cálculo es `Decimal` (integridad financiera: nada de floats monetarios) y
puro: sin red, sin DB, sin efectos. El equity y el gasto de ops entran por
providers inyectables (Track A no implementa el ledger de ops ni el de capital).
El enforcement vive detrás de un puerto inyectable (`apply_capital_risk_actions`)
para que los tests nunca disparen efectos reales. Paper-first: este módulo no
habilita live en ningún camino.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, DecimalException, ROUND_CEILING, ROUND_FLOOR
from typing import Any, Callable, Dict, List, Mapping, Optional, Protocol

logger = logging.getLogger(__name__)

# Defaults de la política CEO. Cambiarlos es una decisión de negocio, no técnica.
DEFAULT_CONTRIBUTED_CAPITAL_USD = "1000"
DEFAULT_KILL_DRAWDOWN_PCT = "0.25"
DEFAULT_DAILY_LOSS_LIMIT_PCT = "0.03"
DEFAULT_ALERT_DRAWDOWN_PCT = "0.15"
# Amendment 01 (Decisión 3): techo de ops <= USD 100 con devengo mensual (~10-15/mes).
DEFAULT_OPS_RESERVE_USD = "100"
# Marca del supuesto usado cuando no hay ops ledger: se toma el techo como
# comprometido y gastado, no el devengado real.
OPS_ASSUMPTION_CEILING = "ops_reserve_total_ceiling"

BASIS_POOL = "pool"
BASIS_TRADING = "trading"
VALID_KILL_BASES = (BASIS_POOL, BASIS_TRADING)
# Decisión CEO 2026-08-05: el kill mide pérdida de estrategia, no gasto operativo.
DEFAULT_KILL_BASIS = BASIS_TRADING

DEFAULT_PAPER_STATE_PATH = "paper_trading_state.json"
DAILY_FLAT_DURATION_SECONDS = 86_400  # 24 h
DAILY_LOSS_BASIS = "trading_equity"

MONEY_QUANT = Decimal("0.01")
PCT_QUANT = Decimal("0.00000001")
PCT_REPORT_QUANT = Decimal("0.000001")

ACTION_KILL_LIQUIDATE = "kill_liquidate_and_replan"
ACTION_EMERGENCY_STOP = "emergency_stop"
ACTION_DAILY_FLAT = "flat_and_disable_trading_24h"
ACTION_ALERT_DRAWDOWN = "notify_drawdown_alert"
ACTION_REVIEW_OPS_BURN = "review_ops_burn_before_liquidating"

SEVERITY_OK = "ok"
SEVERITY_ALERT = "alert"
SEVERITY_DAILY_FLAT = "daily_flat"
SEVERITY_KILL = "kill"

ROLE_KILL = "kill"
ROLE_INFORMATIVE = "informative"


class CapitalRiskInputError(ValueError):
    """Input inválido o ausente: preferimos fallar cerrado antes que asumir."""


def _to_decimal(value: Any, field_name: str) -> Decimal:
    """Normaliza a Decimal pasando por `str` para no arrastrar ruido binario."""
    if value is None or (isinstance(value, str) and not value.strip()):
        raise CapitalRiskInputError(f"{field_name} es requerido y no puede ser vacío")
    if isinstance(value, Decimal):
        candidate = value
    elif isinstance(value, (int, str)):
        try:
            candidate = Decimal(str(value).strip())
        except (DecimalException, ValueError) as exc:
            raise CapitalRiskInputError(
                f"{field_name} no es numérico: {value!r}"
            ) from exc
    elif isinstance(value, float):
        # Aceptado por interoperabilidad con estado paper legado; normalizado via str.
        candidate = Decimal(str(value))
    else:
        raise CapitalRiskInputError(
            f"{field_name} tiene tipo no soportado: {type(value)!r}"
        )
    if not candidate.is_finite():
        raise CapitalRiskInputError(f"{field_name} debe ser finito: {value!r}")
    return candidate


def _quantize_money(value: Decimal, rounding: str = ROUND_FLOOR) -> Decimal:
    return value.quantize(MONEY_QUANT, rounding=rounding)


def _quantize_pct(value: Decimal) -> Decimal:
    # ROUND_FLOOR: al truncar hacia abajo la pérdida nunca se ve mejor de lo real.
    return value.quantize(PCT_QUANT, rounding=ROUND_FLOOR)


def _report_pct(value: Decimal) -> str:
    return str(value.quantize(PCT_REPORT_QUANT, rounding=ROUND_FLOOR))


def _require_positive(value: Decimal, field_name: str) -> Decimal:
    if value <= 0:
        raise CapitalRiskInputError(f"{field_name} debe ser > 0 (recibido {value})")
    return value


def _require_non_negative(value: Decimal, field_name: str) -> Decimal:
    if value < 0:
        raise CapitalRiskInputError(f"{field_name} debe ser >= 0 (recibido {value})")
    return value


def _require_fraction(value: Decimal, field_name: str) -> Decimal:
    if value < 0 or value > 1:
        raise CapitalRiskInputError(
            f"{field_name} debe ser una fracción entre 0 y 1 (recibido {value})"
        )
    return value


def _env_value(source: Mapping[str, str], name: str, default: str) -> str:
    """Una var vacía (habitual en Docker/Heroku) equivale a no seteada."""
    raw = source.get(name)
    if raw is None or not str(raw).strip():
        return default
    return str(raw).strip()


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class CapitalRiskConfig:
    """Umbrales de la política de capital. Inmutable para evitar drift en runtime."""

    contributed_capital: Decimal
    kill_drawdown_pct: Decimal
    daily_loss_limit_pct: Decimal
    alert_drawdown_pct: Decimal
    ops_reserve_usd: Decimal
    kill_basis: str

    @classmethod
    def from_env(cls, env: Optional[Mapping[str, str]] = None) -> "CapitalRiskConfig":
        source = os.environ if env is None else env

        contributed = _require_positive(
            _to_decimal(
                _env_value(
                    source, "CONTRIBUTED_CAPITAL_USD", DEFAULT_CONTRIBUTED_CAPITAL_USD
                ),
                "CONTRIBUTED_CAPITAL_USD",
            ),
            "CONTRIBUTED_CAPITAL_USD",
        )
        ops_reserve = _require_non_negative(
            _to_decimal(
                _env_value(source, "OPS_RESERVE_USD", DEFAULT_OPS_RESERVE_USD),
                "OPS_RESERVE_USD",
            ),
            "OPS_RESERVE_USD",
        )
        if ops_reserve >= contributed:
            raise CapitalRiskInputError(
                "OPS_RESERVE_USD debe ser menor que CONTRIBUTED_CAPITAL_USD "
                f"(recibido {ops_reserve} sobre {contributed}): dejaría capital "
                "tradable <= 0"
            )

        kill_basis = _env_value(source, "KILL_BASIS", DEFAULT_KILL_BASIS).lower()
        if kill_basis not in VALID_KILL_BASES:
            raise CapitalRiskInputError(
                f"KILL_BASIS inválido: {kill_basis!r}. Valores permitidos: "
                f"{', '.join(VALID_KILL_BASES)}"
            )

        return cls(
            contributed_capital=contributed,
            kill_drawdown_pct=_require_fraction(
                _to_decimal(
                    _env_value(source, "KILL_DRAWDOWN_PCT", DEFAULT_KILL_DRAWDOWN_PCT),
                    "KILL_DRAWDOWN_PCT",
                ),
                "KILL_DRAWDOWN_PCT",
            ),
            daily_loss_limit_pct=_require_fraction(
                _to_decimal(
                    _env_value(
                        source, "DAILY_LOSS_LIMIT_PCT", DEFAULT_DAILY_LOSS_LIMIT_PCT
                    ),
                    "DAILY_LOSS_LIMIT_PCT",
                ),
                "DAILY_LOSS_LIMIT_PCT",
            ),
            alert_drawdown_pct=_require_fraction(
                _to_decimal(
                    _env_value(
                        source, "ALERT_DRAWDOWN_PCT", DEFAULT_ALERT_DRAWDOWN_PCT
                    ),
                    "ALERT_DRAWDOWN_PCT",
                ),
                "ALERT_DRAWDOWN_PCT",
            ),
            ops_reserve_usd=ops_reserve,
            kill_basis=kill_basis,
        )


# --------------------------------------------------------------------------- #
# Snapshots de entrada (providers desacoplados)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class EquitySnapshot:
    """Equity de trading reconciliado. Lo produce S6 (`capital_books`) a futuro."""

    equity: Optional[Decimal]
    equity_prev_eod: Optional[Decimal]
    source: str


@dataclass(frozen=True)
class OpsSnapshot:
    """Gasto de ops. Lo produce Track B (`app/core/ops_ledger.py`).

    `reserve_committed` es el **devengado** (no el techo). `assumed=True` significa
    que no hubo ledger y el engine cayó al supuesto de env; `assumption` dice cuál
    fue, para que el dashboard no presente un supuesto como dato.
    """

    reserve_committed: Decimal
    spent: Decimal
    source: str
    assumed: bool
    assumption: Optional[str] = None


# --------------------------------------------------------------------------- #
# Status
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class CapitalRiskStatus:
    """Snapshot evaluado. Sin secrets: apto para dashboard y API read-only."""

    contributed_capital: Decimal
    tradable_capital: Decimal
    equity: Decimal
    equity_trading: Decimal
    equity_pool: Decimal
    kill_basis: str
    other_basis: str
    kill_floor: Decimal
    kill_floor_pool: Decimal
    kill_floor_trading: Decimal
    dd_pool: Decimal
    dd_trading: Decimal
    daily_loss_pct: Optional[Decimal]
    daily_loss_basis: str
    equity_prev_eod: Optional[Decimal]
    alert_triggered: bool
    alert_triggered_pool: bool
    alert_triggered_trading: bool
    alert_bases: List[str]
    kill_triggered: bool
    kill_triggered_pool: bool
    kill_triggered_trading: bool
    kill_triggered_other_basis: bool
    kill_driven_by_ops_burn: bool
    daily_flat_triggered: bool
    daily_baseline_available: bool
    ops_reserve_committed: Decimal
    ops_spent: Decimal
    ops_remaining: Decimal
    ops_overspent: bool
    ops_assumed: bool
    ops_assumption: Optional[str]
    ops_source: str
    severity: str
    actions: List[str]
    reasons: List[str]
    evaluated_at: datetime
    equity_source: Optional[str] = None
    thresholds: Dict[str, str] = field(default_factory=dict)

    @property
    def dd_vs_contributed(self) -> Decimal:
        """Alias de `dd_pool`: es la lectura literal de ADR-003 (vs aportado)."""
        return self.dd_pool

    def _basis_block(self, basis: str) -> Dict[str, Any]:
        is_pool = basis == BASIS_POOL
        return {
            "capital_base": str(
                self.contributed_capital if is_pool else self.tradable_capital
            ),
            "equity": str(self.equity_pool if is_pool else self.equity_trading),
            "kill_floor": str(
                self.kill_floor_pool if is_pool else self.kill_floor_trading
            ),
            "drawdown": _report_pct(self.dd_pool if is_pool else self.dd_trading),
            "kill_triggered": (
                self.kill_triggered_pool if is_pool else self.kill_triggered_trading
            ),
            "alert_triggered": (
                self.alert_triggered_pool if is_pool else self.alert_triggered_trading
            ),
            "role": ROLE_KILL if basis == self.kill_basis else ROLE_INFORMATIVE,
        }

    def to_dict(self) -> Dict[str, Any]:
        """JSON-safe. Montos y fracciones como string para no perder precisión."""
        return {
            "contributed_capital": str(self.contributed_capital),
            "tradable_capital": str(self.tradable_capital),
            "equity": str(self.equity),
            "equity_prev_eod": (
                None if self.equity_prev_eod is None else str(self.equity_prev_eod)
            ),
            "equity_source": self.equity_source,
            "kill_basis": self.kill_basis,
            "other_basis": self.other_basis,
            "kill_floor": str(self.kill_floor),
            "dd_pool": _report_pct(self.dd_pool),
            "dd_trading": _report_pct(self.dd_trading),
            "dd_vs_contributed": _report_pct(self.dd_pool),
            "daily_loss_pct": (
                None if self.daily_loss_pct is None else _report_pct(self.daily_loss_pct)
            ),
            "daily_loss_basis": self.daily_loss_basis,
            "daily_baseline_available": self.daily_baseline_available,
            "alert_triggered": self.alert_triggered,
            "alert_bases": list(self.alert_bases),
            "kill_triggered": self.kill_triggered,
            "kill_triggered_other_basis": self.kill_triggered_other_basis,
            "kill_driven_by_ops_burn": self.kill_driven_by_ops_burn,
            "daily_flat_triggered": self.daily_flat_triggered,
            "bases": {
                BASIS_POOL: self._basis_block(BASIS_POOL),
                BASIS_TRADING: self._basis_block(BASIS_TRADING),
            },
            "ops": {
                "reserve_committed": str(self.ops_reserve_committed),
                "spent": str(self.ops_spent),
                "remaining": str(self.ops_remaining),
                "overspent": self.ops_overspent,
                "assumed": self.ops_assumed,
                "assumption": self.ops_assumption,
                "source": self.ops_source,
            },
            "severity": self.severity,
            "actions": list(self.actions),
            "reasons": list(self.reasons),
            "evaluated_at": self.evaluated_at.isoformat(),
            "thresholds": dict(self.thresholds),
        }


# --------------------------------------------------------------------------- #
# Funciones puras
# --------------------------------------------------------------------------- #


def kill_floor(capital_base: Any, kill_drawdown_pct: Any = None) -> Decimal:
    """Equity mínimo tolerado sobre una base. `ROUND_CEILING`: floor conservador."""
    base = _require_positive(_to_decimal(capital_base, "capital_base"), "capital_base")
    pct = _require_fraction(
        _to_decimal(
            DEFAULT_KILL_DRAWDOWN_PCT
            if kill_drawdown_pct is None
            else kill_drawdown_pct,
            "kill_drawdown_pct",
        ),
        "kill_drawdown_pct",
    )
    return _quantize_money(base * (Decimal("1") - pct), rounding=ROUND_CEILING)


def tradable_capital(contributed: Any, ops_reserve_committed: Any) -> Decimal:
    """Capital que realmente puede operar la estrategia (aportado − reserva ops)."""
    contributed_dec = _require_positive(
        _to_decimal(contributed, "contributed_capital"), "contributed_capital"
    )
    committed = _require_non_negative(
        _to_decimal(ops_reserve_committed, "ops_reserve_committed"),
        "ops_reserve_committed",
    )
    if committed >= contributed_dec:
        raise CapitalRiskInputError(
            f"ops_reserve_committed ({committed}) no puede consumir todo el capital "
            f"aportado ({contributed_dec})"
        )
    return _quantize_money(contributed_dec - committed)


def dd_vs_contributed(equity: Any, capital_base: Any) -> Decimal:
    """Fracción de drawdown vs una base de capital (negativo = pérdida). No usa HWM."""
    equity_dec = _quantize_money(_to_decimal(equity, "equity"))
    base = _require_positive(_to_decimal(capital_base, "capital_base"), "capital_base")
    return _quantize_pct(equity_dec / base - Decimal("1"))


def daily_loss_pct(equity_now: Any, equity_prev_eod: Any) -> Decimal:
    """Variación del día vs equity EOD previo (negativo = pérdida)."""
    now_dec = _quantize_money(_to_decimal(equity_now, "equity"))
    prev_dec = _require_positive(
        _to_decimal(equity_prev_eod, "equity_prev_eod"), "equity_prev_eod"
    )
    return _quantize_pct(now_dec / prev_dec - Decimal("1"))


def evaluate_capital_risk(
    *,
    equity: Any,
    equity_prev_eod: Any = None,
    config: Optional[CapitalRiskConfig] = None,
    ops: Optional[OpsSnapshot] = None,
    equity_source: Optional[str] = None,
    now: Optional[datetime] = None,
) -> CapitalRiskStatus:
    """Evalúa la política completa en ambas bases. Pura salvo `datetime.now`.

    `equity` es el equity **de trading**. Si no se pasa `ops`, se asume el **techo**
    de ops de env (`OPS_RESERVE_USD`) como comprometido y ya gastado, y el status lo
    marca con `ops_assumed=True` + `ops_assumption`.
    """
    cfg = config or CapitalRiskConfig.from_env()
    contributed = _require_positive(
        _to_decimal(cfg.contributed_capital, "contributed_capital"),
        "contributed_capital",
    )
    equity_trading = _quantize_money(_to_decimal(equity, "equity"))

    ops_snapshot = ops or OpsSnapshot(
        reserve_committed=cfg.ops_reserve_usd,
        spent=cfg.ops_reserve_usd,
        source="env_default",
        assumed=True,
        assumption=OPS_ASSUMPTION_CEILING,
    )
    committed = _require_non_negative(
        _to_decimal(ops_snapshot.reserve_committed, "ops_reserve_committed"),
        "ops_reserve_committed",
    )
    spent = _require_non_negative(
        _to_decimal(ops_snapshot.spent, "ops_spent"), "ops_spent"
    )
    tradable = tradable_capital(contributed, committed)
    ops_overspent = spent > committed
    # Sobregasto: el exceso ya salió del equity de trading; el colchón es 0, no negativo.
    ops_remaining = _quantize_money(max(committed - spent, Decimal("0")))
    equity_pool = _quantize_money(equity_trading + ops_remaining)

    floor_pool = kill_floor(contributed, cfg.kill_drawdown_pct)
    floor_trading = kill_floor(tradable, cfg.kill_drawdown_pct)
    dd_pool = dd_vs_contributed(equity_pool, contributed)
    dd_trading = dd_vs_contributed(equity_trading, tradable)

    kill_pool = equity_pool <= floor_pool
    kill_trading = equity_trading <= floor_trading
    basis_is_trading = cfg.kill_basis == BASIS_TRADING
    kill_triggered = kill_trading if basis_is_trading else kill_pool
    kill_other = kill_pool if basis_is_trading else kill_trading
    other_basis = BASIS_POOL if basis_is_trading else BASIS_TRADING
    # Diagnóstico del RISK_BLOCK: el pool se rompe pero la estrategia está sana.
    kill_driven_by_ops_burn = kill_pool and not kill_trading

    alert_pool = dd_pool <= -cfg.alert_drawdown_pct
    alert_trading = dd_trading <= -cfg.alert_drawdown_pct
    alert_bases = [
        basis
        for basis, triggered in ((BASIS_POOL, alert_pool), (BASIS_TRADING, alert_trading))
        if triggered
    ]

    # Un baseline diario ausente o corrupto no debe impedir evaluar el kill.
    daily_pct: Optional[Decimal] = None
    prev_dec: Optional[Decimal] = None
    if equity_prev_eod is not None:
        try:
            prev_dec = _quantize_money(_to_decimal(equity_prev_eod, "equity_prev_eod"))
            daily_pct = daily_loss_pct(equity_trading, prev_dec)
        except CapitalRiskInputError as exc:
            logger.warning("equity_prev_eod inválido, daily loss no evaluado: %s", exc)
            prev_dec = None
            daily_pct = None

    daily_flat_triggered = (
        daily_pct is not None and daily_pct <= -cfg.daily_loss_limit_pct
    )

    actions: List[str] = []
    reasons: List[str] = []

    if kill_triggered:
        actions.extend([ACTION_KILL_LIQUIDATE, ACTION_EMERGENCY_STOP])
        reasons.append(
            f"Kill: equity {equity_trading if basis_is_trading else equity_pool} "
            f"<= kill floor {floor_trading if basis_is_trading else floor_pool} "
            f"(base {cfg.kill_basis})"
        )
    if daily_flat_triggered:
        actions.append(ACTION_DAILY_FLAT)
        reasons.append(
            f"Pérdida diaria {daily_pct} supera el límite "
            f"-{cfg.daily_loss_limit_pct} sobre {DAILY_LOSS_BASIS}"
        )
    if alert_bases:
        actions.append(ACTION_ALERT_DRAWDOWN)
        reasons.append(
            f"Alerta de drawdown -{cfg.alert_drawdown_pct} en base(s): "
            f"{', '.join(alert_bases)}"
        )
    if kill_driven_by_ops_burn:
        actions.append(ACTION_REVIEW_OPS_BURN)
        reasons.append(
            "dd_pool rompe el floor por gasto de ops, no por pérdida de trading "
            f"(ops gastado {spent} de {committed}; dd_trading {dd_trading}). "
            "Revisar devengo de ops antes de liquidar."
        )
    ops_assumption = ops_snapshot.assumption or (
        OPS_ASSUMPTION_CEILING if ops_snapshot.assumed else None
    )
    if ops_assumption == OPS_ASSUMPTION_CEILING:
        # Sin ops ledger tomamos el techo, no el devengado: tradable_capital queda en
        # su mínimo y el kill floor de trading en su valor más bajo. Es un supuesto,
        # no un dato: el devengado real (Track B) sube tradable y sube el floor.
        reasons.append(
            f"ops asumido = techo de reserva ({committed}), no devengado real: "
            f"tradable_capital {tradable} es el mínimo posible y kill floor de "
            f"trading {floor_trading} el más bajo. Dato real: ops ledger (Track B)."
        )

    if kill_triggered:
        severity = SEVERITY_KILL
    elif daily_flat_triggered:
        severity = SEVERITY_DAILY_FLAT
    elif alert_bases:
        severity = SEVERITY_ALERT
    else:
        severity = SEVERITY_OK

    return CapitalRiskStatus(
        contributed_capital=_quantize_money(contributed),
        tradable_capital=tradable,
        equity=equity_trading,
        equity_trading=equity_trading,
        equity_pool=equity_pool,
        kill_basis=cfg.kill_basis,
        other_basis=other_basis,
        kill_floor=floor_trading if basis_is_trading else floor_pool,
        kill_floor_pool=floor_pool,
        kill_floor_trading=floor_trading,
        dd_pool=dd_pool,
        dd_trading=dd_trading,
        daily_loss_pct=daily_pct,
        daily_loss_basis=DAILY_LOSS_BASIS,
        equity_prev_eod=prev_dec,
        alert_triggered=bool(alert_bases),
        alert_triggered_pool=alert_pool,
        alert_triggered_trading=alert_trading,
        alert_bases=alert_bases,
        kill_triggered=kill_triggered,
        kill_triggered_pool=kill_pool,
        kill_triggered_trading=kill_trading,
        kill_triggered_other_basis=kill_other,
        kill_driven_by_ops_burn=kill_driven_by_ops_burn,
        daily_flat_triggered=daily_flat_triggered,
        daily_baseline_available=daily_pct is not None,
        ops_reserve_committed=_quantize_money(committed),
        ops_spent=_quantize_money(spent),
        ops_remaining=ops_remaining,
        ops_overspent=ops_overspent,
        ops_assumed=ops_snapshot.assumed,
        ops_assumption=ops_assumption,
        ops_source=ops_snapshot.source,
        severity=severity,
        actions=actions,
        reasons=reasons,
        evaluated_at=now or datetime.now(timezone.utc),
        equity_source=equity_source,
        thresholds={
            "kill_drawdown_pct": str(cfg.kill_drawdown_pct),
            "daily_loss_limit_pct": str(cfg.daily_loss_limit_pct),
            "alert_drawdown_pct": str(cfg.alert_drawdown_pct),
        },
    )


# --------------------------------------------------------------------------- #
# Enforcement: puerto inyectable, nunca efectos reales desde los tests
# --------------------------------------------------------------------------- #


class CapitalRiskBreakerPort(Protocol):
    """Contrato mínimo de enforcement; el adapter real vive fuera del cálculo."""

    async def emergency_stop(self, reason: str) -> None: ...

    async def disable_trading(self, reason: str, duration_seconds: int) -> None: ...


class LoggingBreakerPort:
    """Puerto por defecto paper-safe: deja rastro y no toca el exchange."""

    def __init__(self, log: Optional[logging.Logger] = None) -> None:
        self._log = log or logger

    async def emergency_stop(self, reason: str) -> None:
        self._log.critical("🚨 [paper-safe] emergency stop solicitado: %s", reason)

    async def disable_trading(self, reason: str, duration_seconds: int) -> None:
        self._log.warning(
            "⛔ [paper-safe] trading deshabilitado %ss: %s", duration_seconds, reason
        )


class CircuitBreakersPort:
    """Adapter duck-typed sobre los circuit breakers del repo (o el router de Track F).

    Sin import duro: se acepta cualquier objeto con `activate_critical_mode()` y
    `activate_breaker(type, reason)`. Construirlo es opt-in explícito; quien lo
    inyecta acepta los efectos.
    """

    def __init__(self, breakers: Any) -> None:
        self._breakers = breakers

    async def emergency_stop(self, reason: str) -> None:
        await self._breakers.activate_critical_mode()
        logger.critical("🚨 capital risk kill → modo crítico activado: %s", reason)

    async def disable_trading(self, reason: str, duration_seconds: int) -> None:
        # TODO(S2-followup): el flag global `trading_enabled=false` por 24 h necesita
        # store persistente (Redis con TTL) + reanudación condicional del runbook
        # §5.2; hoy solo se activa el breaker de integridad.
        await self._breakers.activate_breaker("system_integrity", reason)


def build_breaker_port(breakers: Any = None) -> CapitalRiskBreakerPort:
    """Devuelve el adapter real si hay breakers; si no, el puerto paper-safe."""
    if breakers is None:
        return LoggingBreakerPort()
    return CircuitBreakersPort(breakers)


async def apply_capital_risk_actions(
    status: CapitalRiskStatus,
    breaker_port: Optional[CapitalRiskBreakerPort],
) -> List[str]:
    """Aplica el enforcement derivado del status. Devuelve las acciones ejecutadas."""
    if breaker_port is None:
        raise CapitalRiskInputError("breaker_port es requerido para aplicar acciones")

    applied: List[str] = []
    if status.kill_triggered:
        reason = (
            f"capital risk kill (base {status.kill_basis}): equity {status.equity} "
            f"vs kill floor {status.kill_floor}; dd_trading {status.dd_trading}, "
            f"dd_pool {status.dd_pool}"
        )
        if status.kill_driven_by_ops_burn:
            reason += (
                " — atención: el breach de la base pool viene de gasto de ops "
                f"({status.ops_spent} de {status.ops_reserve_committed}), "
                "no de pérdida de trading"
            )
        await breaker_port.emergency_stop(reason)
        applied.append(ACTION_EMERGENCY_STOP)

    if status.daily_flat_triggered:
        reason = f"daily loss {status.daily_loss_pct} supera el límite diario"
        await breaker_port.disable_trading(reason, DAILY_FLAT_DURATION_SECONDS)
        applied.append(ACTION_DAILY_FLAT)

    return applied


# --------------------------------------------------------------------------- #
# Providers: equity (S6) y ops (Track B). Defaults locales seguros, sin red.
# --------------------------------------------------------------------------- #

EquityProvider = Callable[[], EquitySnapshot]
OpsProvider = Callable[[], OpsSnapshot]


def _safe_decimal(value: Any, field_name: str) -> Optional[Decimal]:
    if value is None:
        return None
    try:
        return _to_decimal(value, field_name)
    except CapitalRiskInputError as exc:
        logger.warning("valor de %s ignorado: %s", field_name, exc)
        return None


def resolve_equity_snapshot(
    env: Optional[Mapping[str, str]] = None,
    state_path: Optional[str] = None,
) -> EquitySnapshot:
    """Default seguro de equity: sin exchange ni DB.

    Prioridad: override por env (dashboards/paper) → estado de paper trading en
    disco → `unavailable` (el endpoint falla cerrado).

    Contrato esperado de S6 (`app/core/capital_books.py`): una función sin
    argumentos que devuelva `EquitySnapshot(equity, equity_prev_eod, source)` con
    el equity **de trading** reconciliado; se inyecta sustituyendo este provider.
    """
    source_env = os.environ if env is None else env
    path = state_path or source_env.get(
        "CAPITAL_RISK_STATE_PATH", DEFAULT_PAPER_STATE_PATH
    )

    equity = _safe_decimal(
        source_env.get("CAPITAL_RISK_EQUITY_USD"), "CAPITAL_RISK_EQUITY_USD"
    )
    prev_eod = _safe_decimal(
        source_env.get("CAPITAL_RISK_EQUITY_PREV_EOD_USD"),
        "CAPITAL_RISK_EQUITY_PREV_EOD_USD",
    )
    if equity is not None:
        return EquitySnapshot(equity=equity, equity_prev_eod=prev_eod, source="env")

    try:
        with open(path, "r", encoding="utf-8") as handle:
            state = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("estado paper no disponible en %s: %s", path, exc)
        return EquitySnapshot(
            equity=None, equity_prev_eod=prev_eod, source="unavailable"
        )

    if not isinstance(state, dict):
        return EquitySnapshot(
            equity=None, equity_prev_eod=prev_eod, source="unavailable"
        )

    equity = _safe_decimal(
        state.get("current_balance", state.get("balance")),
        "paper_state.current_balance",
    )
    if equity is None:
        return EquitySnapshot(
            equity=None, equity_prev_eod=prev_eod, source="unavailable"
        )

    if prev_eod is None:
        prev_eod = _safe_decimal(
            state.get("equity_prev_eod"), "paper_state.equity_prev_eod"
        )
    return EquitySnapshot(equity=equity, equity_prev_eod=prev_eod, source="paper_state")


def resolve_ops_snapshot(
    env: Optional[Mapping[str, str]] = None,
    ledger: Any = None,
) -> OpsSnapshot:
    """Resuelve el gasto de ops sin depender de Track B.

    Contrato esperado del ops ledger (Track B, `app/core/ops_ledger.py`): un objeto
    con `get_ops_snapshot()` que devuelva un mapping con
    `ops_reserve_committed_usd` (el **devengado**, no el techo) y `ops_spent_usd`
    (str/Decimal, USD) y opcionalmente `as_of`.

    Si el ledger no está o falla, se usa `OPS_RESERVE_USD` (default 100 = techo del
    Amendment 01) asumiendo la reserva íntegra comprometida y gastada, y se marca
    `assumed=True` con `assumption=OPS_ASSUMPTION_CEILING`. Ese supuesto da el
    `tradable_capital` mínimo (`dd_pool` en su lectura más dura), así que el número
    no debe sobrevivir al go-live sin el devengado real.
    """
    source_env = os.environ if env is None else env

    if ledger is not None:
        try:
            raw = ledger.get_ops_snapshot()
            committed = _to_decimal(
                raw["ops_reserve_committed_usd"], "ops_reserve_committed_usd"
            )
            spent = _to_decimal(raw["ops_spent_usd"], "ops_spent_usd")
            return OpsSnapshot(
                reserve_committed=committed,
                spent=spent,
                source="ops_ledger",
                assumed=False,
            )
        except Exception as exc:  # noqa: BLE001 - fallback explícito, nunca romper el status
            logger.warning("ops ledger no utilizable, se usa supuesto de env: %s", exc)

    committed = _to_decimal(
        _env_value(source_env, "OPS_RESERVE_USD", DEFAULT_OPS_RESERVE_USD),
        "OPS_RESERVE_USD",
    )
    spent = _safe_decimal(source_env.get("OPS_SPENT_USD"), "OPS_SPENT_USD")
    if spent is None:
        return OpsSnapshot(
            reserve_committed=committed,
            spent=committed,
            source="env_default",
            assumed=True,
            assumption=OPS_ASSUMPTION_CEILING,
        )
    return OpsSnapshot(
        reserve_committed=committed, spent=spent, source="env", assumed=False
    )


__all__ = [
    "ACTION_ALERT_DRAWDOWN",
    "ACTION_DAILY_FLAT",
    "ACTION_EMERGENCY_STOP",
    "ACTION_KILL_LIQUIDATE",
    "ACTION_REVIEW_OPS_BURN",
    "BASIS_POOL",
    "BASIS_TRADING",
    "CapitalRiskBreakerPort",
    "CapitalRiskConfig",
    "CapitalRiskInputError",
    "CapitalRiskStatus",
    "CircuitBreakersPort",
    "DAILY_FLAT_DURATION_SECONDS",
    "EquityProvider",
    "EquitySnapshot",
    "LoggingBreakerPort",
    "OPS_ASSUMPTION_CEILING",
    "OpsProvider",
    "OpsSnapshot",
    "apply_capital_risk_actions",
    "build_breaker_port",
    "daily_loss_pct",
    "dd_vs_contributed",
    "evaluate_capital_risk",
    "kill_floor",
    "resolve_equity_snapshot",
    "resolve_ops_snapshot",
    "tradable_capital",
]
