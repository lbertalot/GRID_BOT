# IC-WIRE + KPI SELL — status paper L0 (AS-3)

| Campo | Valor |
|-------|-------|
| Fecha | **2026-08-10** (update post-#88) |
| Owner | `trader-market-maker` + `trading-backend-tdd` |
| Deadline DoD | **≤ 2026-08-13** |
| Modo | paper-only · sizing **200** · hash `630abf63…` · **PROMOTE_LIVE: NO** |
| Spec | `GRID_BOT/Docs/L0_PAPER_FREEZE_PARAMS.md` §2.3 · ADR `Docs/ADR_IC_WIRE_E7.md` |

## KPI SELL (ventana)

| Métrica | Corte 2026-08-09 | Umbral semanal (AC) | Estado |
|---------|------------------|---------------------|--------|
| Fills / BUY/SELL | 128 · 112/16 | SELL ≥ 10% fills o ≥1 SELL/24h | **PARCIAL** (~12.5%) |
| Ciclos closed | 15 | ≥1/día UTC | parcial |
| Realized net | ≈0.072 | **no** edge claim | NO-GO revenue |

No bajar spacing / no subir sizing.

## IC-WIRE progreso → 08-13

| Control | Estado 08-10 | Residual |
|---------|--------------|----------|
| IC-1 evento + gauge | Cableado | — |
| IC-1 gate BUY bajo piso | Cableado | — |
| IC-1 cancel-all BUY paper sim | **DONE** · `paper_pending_orders` + trip observe | Registrar resting BUY via `add_buy` cuando el grid posteé límites |
| IC-2 evento + DD observe | Cableado | — |
| IC-2 flatten auto en ciclo | **DONE** · `flatten_pending` + `maybe_flatten` en `mark_to_market` | Simulacro A5 evidencia ≤08-20 |
| IC-2 breaker sync | Best-effort sync/async en `_enforce_ic2` | Validar Redis shared en stack local |
| Simulacro desk A5 | Abierto | ≤08-20 (no bloquea gate E7 08-13) |

**Veredicto AS-3 08-10:** `IC_WIRE_ENFORCE` (cancel+flatten cableados) + SELL **PARCIAL**. Gate E7 documentación lista; falta simulacro A5 + KPI SELL sostenido.

## Plan MM restante

1. Digest MM AT_RISK → acción SELL/IC (ya AS-2).
2. ≤08-13: acta go/no-go E7 con logs+métricas post-simulacro parcial o full.
3. **No** live.

## Go / no-go
- Integridad paper IC-A/B: **PROMOTE_PAPER** (código)
- IC DoD 08-13 (simulacro): **ABIERTO**
- Revenue / live: **NO-GO** · **PROMOTE_LIVE: NO**
