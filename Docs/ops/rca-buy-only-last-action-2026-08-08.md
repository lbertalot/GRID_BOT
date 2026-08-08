# RCA — BUY-only paper (80 fills) → fix round-trip

| Campo | Valor |
|-------|-------|
| Fecha | 2026-08-08 |
| Modo | PAPER · PROMOTE_LIVE = NO |
| Owner | EM → backend + MM |

## Síntoma
Ledger: **80 BUY / 0 SELL** · inventory abierto · realized_net=0 · fees acumulados.

## Causas raíz
1. **`AssetConfig.last_action` no persistía** entre ciclos Celery (manager recreado → siempre `None`) → `decide_grid_action` abría BUY una y otra vez.
2. Con precio ≈ nivel medio de la grilla dinámica (±1% spot), `last_action=BUY` dejaba **`action=None`** (ni BUY ni SELL).

## Fix (paper-safe)
1. `resolve_last_grid_action()` — hidrata desde último fill del ledger (`paper_cycle_liquidity.py`).
2. `decide_grid_action` — cerca del nivel **alterna** BUY↔SELL según `last_action`.
3. Tests: `tests/test_last_action_paper_hydrate.py`.

## Verificación
- Ciclo 14:06Z: señal **SELL** @ 1921.18 · fill `fil-5a1aa18cceb2` · fee≈0.01018
- Ledger post: SELL≥1 · `realized_net`>0 (mínimo) — **no** claim de edge

## Non-goal
No bajar spacing / no subir sizing / no live.
