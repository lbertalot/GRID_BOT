# ADR — IC-WIRE E7 (IC-1 / IC-2 paper Core)

| Campo | Valor |
|-------|--------|
| Estado | **Aceptado (enforce IC-A/B 2026-08-10)** |
| Fecha | 2026-08-06 |
| Slice | S-WAVE-E-OBS / E7 |
| Owner | `trader-market-maker` |
| Apoyo | `trading-backend-tdd` |
| Deadline gate | ≤ 2026-08-13 |
| Modo | Paper-only · deployed **200** · PROMOTE_LIVE=NO |

## Contexto

Desk-policy L0 §2.5 exige IC-1 (freno rebuy bajo piso −5%) e IC-2 (flatten Core a −10% del desplegado). Hasta el kickoff solo existían flags en `grid_config_paper_l0.json` metadata — sin runtime. Sin cableado, MaxDD ≤ 10% desplegado no es alcanzable por diseño ante un move ETH ordinario.

## Decisión

1. **Módulo puro** `app/core/inventory_controls.py` (Decimal, sin red): evaluate IC-1/IC-2 + `InventoryControlGuard`.
2. **Enganches mínimos:**
   - Pre-orden BUY: `OptimizedGridManager._execute_trade` → `allows_core_buy()`.
   - Post-marca: `PaperTradingEngine.mark_to_market` → `evaluate_and_enforce_from_paper`.
3. **IC-2** usa DD desde **pico de equity** / `deployed_capital` (mismo número que rojo MaxDD).
4. Tras IC-2: `armed=False`; re-arm solo con `rearm(reason=...)` escrito.
5. Flatten paper vía puerto inyectable `flatten_core_paper` (tests sin side-effects).

## Consecuencias

- (+) Evento+gate paper medibles en ventana sin tocar hash freeze.
- (+) TDD: `tests/test_inventory_controls_ic_wire.py`.
- (−) Cancel-all de límites paper pendientes y flatten auto en Celery cycle = residual ≤ 2026-08-12.
- (−) Breaker Redis sync para IC-2 = apoyo backend ≤ 2026-08-12.
- Simulacro forzado A5 sigue en ≤ 2026-08-20.

## Alternativas rechazadas

- Meter lógica IC dentro de `AutoCircuitBreaker` (lee `trades.profit_loss`, no equity MtM paper SoT).
- Relajar umbral o sizing > 200 (viola freeze / desk).

## Issue list (owner · fecha)

| ID | Trabajo | Owner | Fecha | Estado |
|----|---------|-------|-------|--------|
| IC-A | Cancel BUY pendientes / no re-post bajo piso cuando IC-1 | backend-tdd | 2026-08-11 | **done** 2026-08-10 (`paper_pending_orders`) |
| IC-B | Flatten auto: ciclo llama `flatten_core_paper` + ledger | MM + backend | 2026-08-12 | **done** 2026-08-10 (`mark_to_market`) |
| IC-C | Activar `system_integrity` sync/async compartido en trip IC-2 | backend-tdd | 2026-08-12 | **partial** best-effort |
| IC-D | Grafana panel IC gauges + alerta paper-aware | devops (E3) | 2026-08-10 | abierto |
| IC-E | Simulacro A5 evidencia tear | MM + devops | 2026-08-20 | **done** 2026-08-10 (`scripts/simulacro_ic_a5_paper.py` · PASS aislado) |
