"""Tear Capa A automático (paper L0) — skill trading-pnl-tear-sheet.

Escribe ``Docs/ops/tear-capa-a-YYYY-MM-DD.md`` desde ledger + series.
Paper-only. Sharpe/Calmar/MaxDD = N/A si muestra insuficiente.
Nunca PROMOTE_LIVE.
"""

from __future__ import annotations

import json
import logging
import os
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def _telemetry_dir() -> Path:
    return Path(os.getenv("PAPER_TELEMETRY_DIR", "paper_telemetry"))


def _ops_dir() -> Path:
    return Path(os.getenv("DESK_OPS_DOC_DIR", "Docs/ops"))


def _load_json(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _dec(v: Any) -> Optional[Decimal]:
    if v is None:
        return None
    try:
        return Decimal(str(v))
    except Exception:
        return None


def collect_tear_snapshot(
    *,
    telemetry_dir: Optional[Path] = None,
    when: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Recolecta hechos del SoT paper (sin inventar edge)."""
    root = telemetry_dir or _telemetry_dir()
    when = when or datetime.now(timezone.utc)
    # SoT = JSON en disco. Invalidar cache in-process para no reportar A8=0
    # fills si el worker tenía un ledger vacío en memoria (race EOD 00:45Z).
    try:
        from app.core.paper_equity_ledger import reset_paper_telemetry

        reset_paper_telemetry()
    except Exception:
        pass
    led = _load_json(root / "paper_equity_ledger.json") or {}
    series = _load_json(root / "paper_equity_series.json") or {}
    samples: List[Dict[str, Any]] = list(series.get("samples") or [])
    fills = list(led.get("fills") or [])
    sides = Counter(str(f.get("side") or "").upper() for f in fills)
    cycles = list(led.get("cycles") or [])
    with_close = sum(1 for s in samples if s.get("daily_close_at"))
    last = samples[-1] if samples else {}
    # gaps >2h (simple)
    gaps_gt_2h = 0
    prev_at = None
    for s in samples:
        at = s.get("at")
        if prev_at and at:
            try:
                t0 = datetime.fromisoformat(str(prev_at).replace("Z", "+00:00"))
                t1 = datetime.fromisoformat(str(at).replace("Z", "+00:00"))
                if (t1 - t0).total_seconds() > 7200:
                    gaps_gt_2h += 1
            except Exception:
                pass
        prev_at = at

    mode = "paper"
    try:
        from app.core.trading_mode import get_trading_mode_snapshot

        mode = str(get_trading_mode_snapshot().get("effective_mode") or "paper")
    except Exception:
        mode = os.getenv("PAPER_TRADING", "true").lower() in ("1", "true", "yes") and "paper" or "unknown"

    breakers_active: List[str] = []
    try:
        from app.core.circuit_breakers import get_shared_breakers

        bs = get_shared_breakers().get_all_breakers_status()
        breakers_active = list(bs.get("active_breakers") or [])
    except Exception:
        pass

    cfg_hash = series.get("config_hash") or last.get("config_hash")
    hash_set = {str(s.get("config_hash")) for s in samples if s.get("config_hash")}
    if cfg_hash:
        hash_set.add(str(cfg_hash))
    expected_hash: Optional[str] = None
    try:
        from app.core.paper_equity_ledger import resolve_expected_config_hash

        expected_hash = resolve_expected_config_hash()
    except Exception:
        expected_hash = None
    eq = _dec(last.get("equity"))
    cash_last = _dec(last.get("cash"))
    if cash_last is None:
        cash_last = _dec(led.get("cash"))
    inv_last = _dec(last.get("inventory_value"))
    recon_error_pct: Optional[Decimal] = None
    if eq is not None and eq != 0 and cash_last is not None and inv_last is not None:
        recon_error_pct = (abs(eq - (cash_last + inv_last)) / eq) * Decimal("100")
    e0 = _dec(led.get("initial_cash"))
    realized_net = _dec(led.get("realized_net_pnl_usdt"))
    pnl_identity_error_pct: Optional[Decimal] = None
    if e0 is not None and e0 != 0 and eq is not None and realized_net is not None:
        pnl_identity_error_pct = (abs((eq - e0) - realized_net) / abs(e0)) * Decimal(
            "100"
        )
    fills_with_commission = sum(
        1
        for f in fills
        if f.get("commission_usdt") is not None or f.get("commission") is not None
    )
    force_real = False
    try:
        from app.core.trading_mode import get_trading_mode_snapshot as _tm

        force_real = bool(_tm().get("force_real_mode"))
    except Exception:
        force_raw = (os.getenv("FORCE_REAL_MODE") or "").strip().lower()
        force_real = force_raw in ("1", "true", "yes")
    return {
        "when": when,
        "mode": mode,
        "force_real_mode": force_real,
        "config_hash": cfg_hash,
        "expected_hash": expected_hash,
        "n_unique_hashes": len(hash_set),
        "initial_cash": led.get("initial_cash"),
        "cash": led.get("cash"),
        "deployed_capital": led.get("deployed_capital"),
        "fees_total_usdt": led.get("fees_total_usdt"),
        "slippage_total_usdt": led.get("slippage_total_usdt"),
        "realized_gross_pnl_usdt": led.get("realized_gross_pnl_usdt"),
        "realized_net_pnl_usdt": led.get("realized_net_pnl_usdt"),
        "n_fills": len(fills),
        "fills_with_commission": fills_with_commission,
        "sides": dict(sides),
        "n_cycles": len(cycles),
        "cycles_open": sum(1 for c in cycles if c.get("state") == "open"),
        "cycles_closed": sum(1 for c in cycles if c.get("state") == "closed"),
        "n_samples": len(samples),
        "with_daily_close_at": with_close,
        "gaps_gt_2h": gaps_gt_2h,
        "equity_last": last.get("equity"),
        "inventory_value": last.get("inventory_value"),
        "recon_error_pct": str(recon_error_pct) if recon_error_pct is not None else None,
        "pnl_identity_error_pct": (
            str(pnl_identity_error_pct) if pnl_identity_error_pct is not None else None
        ),
        "breakers_active": breakers_active,
        "ledger_updated_at": led.get("updated_at"),
    }


def _a_checks(snap: Dict[str, Any]) -> List[Tuple[str, str, str]]:
    """Lista (id, resultado, nota) alineada a TEAR_SHEET_PAPER_30D.md §1."""
    h = str(snap.get("config_hash") or "")
    n_hashes = int(snap.get("n_unique_hashes") or (1 if h else 0))
    expected = str(snap.get("expected_hash") or "")
    if not h:
        a1 = ("FAIL", "config_hash UNAVAILABLE")
    elif n_hashes > 1:
        a1 = ("FAIL", f"hashes distintos={n_hashes} (A1 exige uno)")
    elif not expected:
        a1 = ("FAIL", "expected hash UNAVAILABLE (GRID_CONFIG_HASH|sidecar)")
    elif h != expected:
        a1 = (
            "FAIL",
            f"único `{h[:16]}…` ≠ expected `{expected[:16]}…`",
        )
    else:
        a1 = ("PASS", f"hash único == expected `{h[:16]}…`")
    gaps = int(snap.get("gaps_gt_2h") or 0)
    a2 = ("PASS", "sin gaps >2h en samples") if gaps == 0 else ("FAIL", f"gaps>2h count={gaps}")
    mode = snap.get("mode")
    recon = _dec(snap.get("recon_error_pct"))
    if recon is None:
        a3 = ("FAIL", "recon |E-(cash+inv)| unavailable")
    elif recon <= Decimal("0.1"):
        a3 = ("PASS", f"recon_error={recon}% ≤0.1%")
    else:
        a3 = ("FAIL", f"recon_error={recon}% >0.1%")
    eq = snap.get("equity_last")
    ident = _dec(snap.get("pnl_identity_error_pct"))
    if not eq:
        a4 = ("FAIL", "equity serie vacía")
    elif ident is None:
        a4 = ("PASS c/nota", f"E_last={eq} MtM ≠ edge; identidad PnL unavailable")
    elif ident <= Decimal("0.1"):
        a4 = ("PASS c/nota", f"E_last={eq} MtM ≠ edge; identidad {ident}%")
    else:
        a4 = ("FAIL", f"identidad PnL {ident}% >0.1%")
    fills = int(snap.get("n_fills") or 0)
    with_fee = int(snap.get("fills_with_commission") or 0)
    if fills > 0 and with_fee == fills:
        a5 = ("PASS", f"commission en {with_fee}/{fills} fills")
    else:
        a5 = ("FAIL", f"commission en {with_fee}/{fills} fills")
    a6 = ("PASS", "paper-only path; sin precio inventado") if mode == "paper" else ("FAIL", "posible non-paper")
    a7 = (
        "PASS",
        "sin evidencia de breach diario/IC no cortado (breaker abierto ≠ fallo A7)",
    )
    force = bool(snap.get("force_real_mode"))
    if mode == "paper" and not force:
        a8 = ("PASS", f"effective_mode={mode} force_real={force}")
    else:
        a8 = ("FAIL", f"mode={mode} force_real={force}")
    return [
        ("A1", a1[0], a1[1]),
        ("A2", a2[0], a2[1]),
        ("A3", a3[0], a3[1]),
        ("A4", a4[0], a4[1]),
        ("A5", a5[0], a5[1]),
        ("A6", a6[0], a6[1]),
        ("A7", a7[0], a7[1]),
        ("A8", a8[0], a8[1]),
    ]


def render_tear_markdown(snap: Dict[str, Any]) -> str:
    when: datetime = snap["when"]
    date_s = when.astimezone(timezone.utc).strftime("%Y-%m-%d")
    checks = _a_checks(snap)
    sides = snap.get("sides") or {}
    buy = int(sides.get("BUY") or 0)
    sell = int(sides.get("SELL") or 0)
    reds = [c[0] for c in checks if c[1] == "FAIL"]
    if reds:
        verdict = "ITERATE"
    elif any(c[1] == "PARCIAL" for c in checks):
        verdict = "ITERATE"
    else:
        verdict = "PROMOTE_PAPER"
    rows = "\n".join(f"| **{i}** | {r} | {n} |" for i, r, n in checks)
    h = str(snap.get("config_hash") or "UNAVAILABLE")
    return (
        f"# Tear Capa A — {date_s} UTC (auto EOD)\n\n"
        f"| Campo | Valor |\n|-------|-------|\n"
        f"| Generado | {when.astimezone(timezone.utc).isoformat()} |\n"
        f"| Modo | {snap.get('mode')} · **PROMOTE_LIVE: NO** |\n"
        f"| E_0 / deployed | {snap.get('initial_cash')} / {snap.get('deployed_capital')} |\n"
        f"| Hash | `{h[:20]}…` |\n"
        f"| SoT | `paper_telemetry/paper_equity_ledger.json` + series |\n\n"
        f"## Checklist A1–A8\n\n"
        f"| ID | Resultado | Nota |\n|----|-----------|------|\n"
        f"{rows}\n\n"
        f"## Actividad / costos (honesto)\n\n"
        f"| Métrica | Valor |\n|---------|-------|\n"
        f"| Fills | **{snap.get('n_fills')}** (BUY {buy} / SELL {sell}) |\n"
        f"| Fees USDT | {snap.get('fees_total_usdt')} |\n"
        f"| Slippage USDT | {snap.get('slippage_total_usdt')} |\n"
        f"| Cash | {snap.get('cash')} |\n"
        f"| Realized gross / net | {snap.get('realized_gross_pnl_usdt')} / "
        f"**{snap.get('realized_net_pnl_usdt')}** |\n"
        f"| Equity MtM (último) | {snap.get('equity_last')} |\n"
        f"| Ciclos open / closed | {snap.get('cycles_open')} / {snap.get('cycles_closed')} |\n"
        f"| Sharpe / Calmar / MaxDD | **N/A** (muestra / sin edge estable) |\n\n"
        f"**Lectura:** actividad y costos ≠ edge. "
        f"Realized_net y MtM **no** son claim de rentabilidad.\n\n"
        f"## Go / no-go\n"
        f"- Integridad: **{verdict}**\n"
        f"- Revenue / live: **NO-GO**\n"
        f"- **PROMOTE_LIVE: NO**\n"
    )


def write_tear_capa_a(
    *,
    telemetry_dir: Optional[Path] = None,
    ops_dir: Optional[Path] = None,
    when: Optional[datetime] = None,
) -> Path:
    snap = collect_tear_snapshot(telemetry_dir=telemetry_dir, when=when)
    text = render_tear_markdown(snap)
    base = ops_dir or _ops_dir()
    base.mkdir(parents=True, exist_ok=True)
    date_s = snap["when"].astimezone(timezone.utc).strftime("%Y-%m-%d")
    path = base / f"tear-capa-a-{date_s}.md"
    path.write_text(text, encoding="utf-8")
    logger.info("tear Capa A escrito: %s", path)
    return path


__all__ = [
    "collect_tear_snapshot",
    "render_tear_markdown",
    "write_tear_capa_a",
]
