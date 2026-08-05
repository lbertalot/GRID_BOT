"""Trading mode snapshot for API clarity (paper vs real).

Paper-first: effective_mode prefers simulation unless explicitly armed.
No secrets are included in the snapshot.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Literal

EffectiveMode = Literal["paper", "real_blocked", "real_armed"]


def _env_bool(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).lower() in {"1", "true", "yes", "on"}


def compute_effective_mode(
    *,
    paper_trading: bool,
    force_real_mode: bool,
    trading_enabled: bool,
    emergency_stop: bool,
) -> EffectiveMode:
    """Derive a single UX-facing mode label.

    - paper: simulation path (default-safe)
    - real_blocked: would-be real but not armed / stopped / disabled
    - real_armed: real trading flags set (still requires human live gate operationally)
    """
    if paper_trading and not force_real_mode:
        return "paper"
    if emergency_stop or not trading_enabled or not force_real_mode:
        return "real_blocked"
    return "real_armed"


def get_trading_mode_snapshot() -> Dict[str, Any]:
    paper_trading = _env_bool("PAPER_TRADING", "false")
    force_real_mode = _env_bool("FORCE_REAL_MODE", "false")
    trading_enabled = _env_bool("TRADING_ENABLED", "true")
    emergency_stop = _env_bool("EMERGENCY_STOP", "false")
    binance_testnet = _env_bool("BINANCE_TESTNET", "false")

    effective_mode = compute_effective_mode(
        paper_trading=paper_trading,
        force_real_mode=force_real_mode,
        trading_enabled=trading_enabled,
        emergency_stop=emergency_stop,
    )

    return {
        "paper_trading": paper_trading,
        "force_real_mode": force_real_mode,
        "trading_enabled": trading_enabled,
        "emergency_stop": emergency_stop,
        "binance_testnet": binance_testnet,
        "effective_mode": effective_mode,
    }
