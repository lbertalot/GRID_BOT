"""Utilidades puras: klines Binance → closes y retornos simples."""

from __future__ import annotations

from typing import Any, Sequence


def closes_from_binance_klines(klines: Sequence[Sequence[Any]]) -> list[float]:
    """
    Extrae precios de cierre de klines estilo Binance REST.
    Cada elemento: [open_time, open, high, low, close, volume, ...].
    """
    closes: list[float] = []
    for row in klines:
        try:
            closes.append(float(row[4]))
        except (IndexError, TypeError, ValueError):
            continue
    return closes


def simple_returns_from_closes(closes: Sequence[float]) -> list[float]:
    """Retornos simples (pct_change) entre cierres consecutivos."""
    if len(closes) < 2:
        return []
    out: list[float] = []
    prev = float(closes[0])
    for c in closes[1:]:
        cur = float(c)
        if prev <= 0.0:
            out.append(0.0)
        else:
            out.append((cur - prev) / prev)
        prev = cur
    return out
