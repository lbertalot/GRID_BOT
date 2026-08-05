"""Trading mode snapshot for API clarity (paper vs real).

Paper-first: effective_mode prefers simulation unless explicitly armed.
No secrets are included in the snapshot.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Literal

from app.core.live_gate import gate_allows_real

EffectiveMode = Literal["paper", "real_blocked", "real_armed"]


def _env_bool(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).lower() in {"1", "true", "yes", "on"}


def compute_effective_mode(
    *,
    paper_trading: bool,
    force_real_mode: bool,
    trading_enabled: bool,
    emergency_stop: bool,
    live_gate_signed: bool = False,
) -> EffectiveMode:
    """Derive a single UX-facing mode label.

    - paper: simulation path (default-safe)
    - real_blocked: would-be real but not armed / stopped / disabled / ungated
    - real_armed: real trading flags set *and* live gate dual signoff present

    ``live_gate_signed`` (ADR-007) defaults to ``False`` and that default is a
    control, not a convenience: **omitting it means "gate not verified", so the
    result can never be ``real_armed``** — not even with ``FORCE_REAL_MODE=true``.
    A caller that forgets to propagate the gate state gets the safe answer.
    Only pass ``True`` after verifying the dual signoff, which is what
    ``get_trading_mode_snapshot()`` does via ``gate_allows_real()``.
    """
    if paper_trading and not force_real_mode:
        return "paper"
    if emergency_stop or not trading_enabled or not force_real_mode:
        return "real_blocked"
    if not live_gate_signed:
        return "real_blocked"
    return "real_armed"


def get_trading_mode_snapshot() -> Dict[str, Any]:
    paper_trading = _env_bool("PAPER_TRADING", "false")
    force_real_mode = _env_bool("FORCE_REAL_MODE", "false")
    trading_enabled = _env_bool("TRADING_ENABLED", "true")
    emergency_stop = _env_bool("EMERGENCY_STOP", "false")
    binance_testnet = _env_bool("BINANCE_TESTNET", "false")
    # Fail-closed: an unreadable or unsigned gate resolves to False.
    live_gate_signed = gate_allows_real()

    effective_mode = compute_effective_mode(
        paper_trading=paper_trading,
        force_real_mode=force_real_mode,
        trading_enabled=trading_enabled,
        emergency_stop=emergency_stop,
        live_gate_signed=live_gate_signed,
    )

    return {
        "paper_trading": paper_trading,
        "force_real_mode": force_real_mode,
        "trading_enabled": trading_enabled,
        "emergency_stop": emergency_stop,
        "binance_testnet": binance_testnet,
        "live_gate_signed": live_gate_signed,
        "effective_mode": effective_mode,
    }
