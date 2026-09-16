# ADR-016 addendum — SoT vigente = JSON hasta flip

**Fecha:** 2026-09-13  
**Estado:** vigente (paper-only) · **PROMOTE_LIVE: NO**  
**Padre:** [ADR-016](ADR-016-paper-ledger-postgres-reduce-only.md)  
**Spike:** [spike-pg-ledger-flip.md](spike-pg-ledger-flip.md)  
**Contrato desk:** [`Docs/squad/action-plan-post-retro-30d-GRID_BOT-2026-09-13.md`](../../../Docs/squad/action-plan-post-retro-30d-GRID_BOT-2026-09-13.md) WS A

Este addendum **no** revoca ADR-016. Corrige el claim de runtime: el target «PostgreSQL autoritativo / JSON = export» **aún no está flippeado**.

---

## Decisión (SoT vigente)

Hasta un flip explícito documentado en acta Desk + PR:

| Artefacto | Rol **hoy** (código) |
|-----------|----------------------|
| `paper_telemetry/paper_equity_ledger.json` | **SoT read+write** hot path (`get_paper_ledger()` → `PaperEquityLedger.load` / `_autosave`) |
| `paper_telemetry/paper_equity_series.json` | **SoT** A2 / MaxDD (`get_paper_equity_series()`); misma clase de persistencia JSON |
| Postgres `paper_ledger_*` | Schema + backfill one-shot + helpers REDUCE_ONLY; **no** SoT del desk ni de tears Capa A |
| Tears `desk_tear_capa_a.collect_tear_snapshot` | Lee **solo JSON** |

**Prohibido afirmar** «cutover ADR-016 completo» o «JSON = export de solo lectura» mientras `get_paper_ledger` y los tears sigan el filesystem.

## Qué ya existe (no rehacer)

- Modelos [`app/models/paper_ledger.py`](../../app/models/paper_ledger.py).
- Alembic `20260827_paper_ledger` + `20260827_paper_ledger_full` (incluye `paper_ledger_equity_samples`).
- Script [`scripts/backfill_paper_ledger_pg.py`](../../scripts/backfill_paper_ledger_pg.py) (window `legacy-json-v1`).
- `reserve_reduce_only` / `settle_reduce_only` en [`app/services/paper_ledger_repository.py`](../../app/services/paper_ledger_repository.py) — **sin callers** en `app/core` / ciclo de fills.

## Qué falta (gate del spike, no de este addendum)

1. Validación DBA: schema + **índices concurrentes** + script **`down`** testeado.
2. Dual-write / TDD de lectura **después** de (1).
3. Flip de `get_paper_ledger` + tears → PG, o posponer con este addendum intacto.
4. Decisión de serie equity (G18/G19) unida en T2 — el lock interim JSON **no espera** al flip.

## Won't

- Live / `FORCE_REAL_MODE` / wipe ledger o Redis.
- Dual-write o flip de lectura en el sprint Pre-T0.
- Reescribir samples históricos ni backfill silencioso a la serie JSON.

## Rollback

Ningún cambio de SoT que revertir: el runtime **sigue en JSON**. Si un flip futuro degrada paper, el rollback es no-flip + `REVIEW_REQUIRED` (ADR-016), nunca fail-open de breakers.

**PROMOTE_LIVE: NO.**
