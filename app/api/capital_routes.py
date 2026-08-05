"""Read-only capital books API (P0 slice S6, ADR-004).

`GET /api/capital/books` expone las allocations 70/20/10, los notional caps derivados
del capital tradable y el consolidado que consume el dashboard CEO (ADR-005).

Read-only a propósito: `POST /api/capital/allocations` (ADR-004) queda como follow-up
P1. Cambiar una allocation en L0 es una edición revisada de `config/capital_books.json`,
que deja historia en git, no un POST sin auditoría.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from app.core.capital_books import (
    CapitalBooksConfigError,
    get_books_snapshot,
    serialize_books_snapshot,
    validate_capital_books_config,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/capital", tags=["capital"])


def _log_startup_validation() -> None:
    """Valida la config al importar el router: el error se ve al arrancar, no en el
    primer request del CEO. No tumba la app porque ningún path de trading depende
    todavía del ledger; el endpoint responde 503 mientras la config esté rota."""
    try:
        validate_capital_books_config()
    except CapitalBooksConfigError as exc:
        logger.critical("❌ config de capital books inválida: %s", exc)


_log_startup_validation()


@router.get("/books")
async def get_capital_books() -> Dict[str, Any]:
    """Books declarados + consolidado. Sin secrets, sin datos de cuenta."""
    try:
        return serialize_books_snapshot(get_books_snapshot())
    except CapitalBooksConfigError as exc:
        # Dato ausente > dato mentiroso: no devolvemos ceros ni caps inventados.
        raise HTTPException(
            status_code=503, detail=f"config de capital books inválida: {exc}"
        )
