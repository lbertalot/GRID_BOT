"""Incidente Binance −2015 / IP bloqueada: un canal, cadencia 6–12 h.

No toca whitelist, keys ni el HASH de breakers. Paper-only · PROMOTE_LIVE: NO.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

IP_CHANNEL = "binance_auth_ip"
IP_FLAG_CHANNEL = "binance_auth_ip_flag"
REDIS_FLAG_KEY = "gridbot:binance_auth_ip_blocked"


def persist_binance_auth_ip_blocked(blocked: bool, *, now: Optional[float] = None) -> None:
    from app.core.telegram_ceo_copy import _redis_client, _save_last

    ts = time.time() if now is None else now
    _save_last(IP_FLAG_CHANNEL, "1" if blocked else "0", ts)
    client = _redis_client()
    if client is None:
        return
    try:
        client.set(REDIS_FLAG_KEY, "1" if blocked else "0")
    except Exception as exc:
        logger.debug("binance auth ip flag redis: %s", exc)


def load_binance_auth_ip_blocked() -> bool:
    from app.core.telegram_ceo_copy import _load_last, _redis_client

    client = _redis_client()
    if client is not None:
        try:
            raw = client.get(REDIS_FLAG_KEY)
            if raw is not None:
                return str(raw) in ("1", "true", "True", b"1")
        except Exception:
            pass
    last = _load_last(IP_FLAG_CHANNEL)
    return bool(last and str(last[0]) == "1")


def process_binance_auth_ip_watch(
    *,
    blocked: bool,
    public_ip: str = "",
    location_restricted: bool = False,
    python_binance_auth_ok: bool = False,
    now: Optional[float] = None,
) -> Optional[str]:
    """Copy CEO del incidente IP. None = silencio (debounce)."""
    from app.core.telegram_ceo_copy import (
        _load_last,
        _save_last,
        ceo_plain_enabled,
        hold_si_min_repeat_s,
        render_binance_auth_ip_recovered_telegram,
        render_invalid_ip_telegram,
        should_emit_ceo,
    )

    if not ceo_plain_enabled():
        persist_binance_auth_ip_blocked(blocked, now=now)
        return None

    ts = time.time() if now is None else now
    persist_binance_auth_ip_blocked(blocked, now=ts)
    last = _load_last(IP_CHANNEL)
    prev_fp = str(last[0] if last else "")

    if blocked:
        fp = f"blocked|{int(bool(location_restricted))}"
        if should_emit_ceo(
            IP_CHANNEL,
            fp,
            min_repeat_s=hold_si_min_repeat_s(),
            now=ts,
        ):
            ip = (public_ip or "").strip() or "desconocida"
            note = ""
            if ip != "desconocida":
                note = (
                    "\nIP local observada (puede no ser la de egreso a Binance si hay proxy)."
                )
            body = render_invalid_ip_telegram(
                ip, location_restricted=location_restricted
            )
            return body + note
        return None

    if python_binance_auth_ok and prev_fp.startswith("blocked"):
        if should_emit_ceo(IP_CHANNEL, "recovered", force=True, now=ts):
            return render_binance_auth_ip_recovered_telegram()
        return None
    if not prev_fp.startswith("blocked"):
        _save_last(IP_CHANNEL, "clear", ts)
    return None


__all__ = [
    "IP_CHANNEL",
    "REDIS_FLAG_KEY",
    "load_binance_auth_ip_blocked",
    "persist_binance_auth_ip_blocked",
    "process_binance_auth_ip_watch",
]
