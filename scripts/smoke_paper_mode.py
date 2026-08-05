#!/usr/bin/env python3
"""Smoke de modo paper: verifica que la API reporta effective_mode=paper.

Dos modos de ejecución:

  --http (default)  Golpea una API ya levantada (docker compose / uvicorn local).
  --asgi            Monta la app en proceso vía ASGI, sin servidor ni docker.
                    Útil cuando el daemon de Docker no está disponible.

Nunca escribe ni requiere credenciales reales. Falla (exit 1) si el modo
efectivo no es paper, de modo que sirve como gate del checklist paper.

Uso:
    python scripts/smoke_paper_mode.py
    python scripts/smoke_paper_mode.py --base-url http://localhost:8000
    python scripts/smoke_paper_mode.py --asgi
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EXPECTED_MODE = "paper"
JSON_ENDPOINTS = ("/health", "/health/trading-mode")


def _print(status: str, msg: str) -> None:
    print(f"[{status}] {msg}")


def _check_snapshot(path: str, payload: dict) -> bool:
    trading = payload.get("trading") or {}
    mode = trading.get("effective_mode")
    if mode == EXPECTED_MODE:
        _print("PASS", f"{path} → effective_mode={mode} {json.dumps(trading)}")
        return True
    _print("FAIL", f"{path} → effective_mode={mode!r} (esperado {EXPECTED_MODE!r})")
    return False


async def _run_asgi() -> bool:
    """Ejecuta el smoke contra la app en proceso (sin lifespan ni servidor)."""
    sys.path.insert(0, str(REPO_ROOT))
    # Defaults paper-safe: solo se aplican si el operador no definió nada.
    os.environ.setdefault("PAPER_TRADING", "true")
    os.environ.setdefault("ENVIRONMENT", "development")
    os.environ.setdefault("SECRET_KEY", "smoke-paper-local-key")

    import httpx  # import diferido: el modo --http también lo usa

    from app.main import app

    ok = True
    transport = httpx.ASGITransport(app=app)
    # TrustedHostMiddleware rechaza hosts arbitrarios: usar localhost.
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost:8000") as client:
        for path in JSON_ENDPOINTS:
            response = await client.get(path)
            if response.status_code != 200:
                _print("FAIL", f"{path} → HTTP {response.status_code}")
                ok = False
                continue
            ok = _check_snapshot(path, response.json()) and ok

        metrics = await client.get("/metrics")
        if metrics.status_code == 200 and metrics.text:
            _print("PASS", f"/metrics → HTTP 200 ({len(metrics.text)} bytes)")
        else:
            _print("FAIL", f"/metrics → HTTP {metrics.status_code}")
            ok = False
    return ok


def _run_http(base_url: str, timeout: float) -> bool:
    import httpx

    ok = True
    with httpx.Client(base_url=base_url, timeout=timeout) as client:
        for path in JSON_ENDPOINTS:
            try:
                response = client.get(path)
            except httpx.HTTPError as exc:
                _print("FAIL", f"{path} → error de red: {exc}")
                return False
            if response.status_code != 200:
                _print("FAIL", f"{path} → HTTP {response.status_code}")
                ok = False
                continue
            ok = _check_snapshot(path, response.json()) and ok

        try:
            metrics = client.get("/metrics")
        except httpx.HTTPError as exc:
            _print("FAIL", f"/metrics → error de red: {exc}")
            return False
        if metrics.status_code == 200 and metrics.text:
            _print("PASS", f"/metrics → HTTP 200 ({len(metrics.text)} bytes)")
        else:
            _print("FAIL", f"/metrics → HTTP {metrics.status_code}")
            ok = False
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke de modo paper para GridBot")
    parser.add_argument(
        "--asgi",
        action="store_true",
        help="Montar la app en proceso en lugar de golpear una API levantada",
    )
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args()

    target = "ASGI in-process" if args.asgi else args.base_url
    print(f"--- Smoke paper mode ({target}) ---")

    ok = asyncio.run(_run_asgi()) if args.asgi else _run_http(args.base_url, args.timeout)

    if ok:
        print("\n[PASS] Stack en modo PAPER: effective_mode=paper y /metrics up")
        return 0
    print("\n[FAIL] El stack NO está en modo paper verificable. No promover.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
