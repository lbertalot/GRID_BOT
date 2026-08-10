# IC-WIRE + KPI SELL — status paper L0 (AS-3)

| Campo | Valor |
|-------|-------|
| Fecha | **2026-08-10** (post-#89 + A5) |
| Owner | `trader-market-maker` + `trading-backend-tdd` |
| Deadline DoD | **≤ 2026-08-13** |
| Modo | paper-only · sizing **200** · hash `630abf63…` · **PROMOTE_LIVE: NO** |
| Spec | `Docs/L0_PAPER_FREEZE_PARAMS.md` §2.3 · ADR `Docs/ADR_IC_WIRE_E7.md` |

## KPI SELL (ventana) — refresh runtime

| Métrica | Corte 2026-08-10 (~12:50Z) | Umbral semanal (AC) | Estado |
|---------|----------------------------|---------------------|--------|
| Fills total | **284** | — | OK |
| BUY / SELL | **190 / 94** (~33% SELL) | SELL ≥ 10% fills **o** ≥1 SELL/24h | **ON_TRACK** |
| SELL/24h | **86** (BUY 86 / SELL 86) | ≥1 SELL/24h | **ON_TRACK** |
| Ciclos open / closed | 97 / 93 | ≥1 closed/día | **ON_TRACK** |
| Fees / realized net | ≈2.87 / ≈0.145 | **no** edge claim | honesto / NO-GO revenue |

No bajar spacing / no subir sizing. MtM ≠ edge.

## IC-WIRE progreso → 08-13

| Control | Estado 08-10 | Residual |
|---------|--------------|----------|
| IC-1 evento + gauge + gate BUY | Cableado (#89) | — |
| IC-1 cancel-all BUY paper sim | **DONE** #89 | Paper path hoy = MARKET fill inmediato; book listo para LIMIT resting |
| IC-2 flatten auto mark_to_market | **DONE** #89 | — |
| Simulacro desk A5 | **PASS** · `IC_A5_SIMULACRO_2026-08-10.md` · script aislado | Re-run opcional en CI |
| IC-2 breaker Redis shared | Best-effort | Validar en ops si reaparece stale |

**Veredicto AS-3 08-10:** `IC_WIRE_ENFORCE` + SELL **ON_TRACK** + A5 **PASS**.  
Gate E7 código+drill: **GO paper**. Live: **NO**.

## Go / no-go
- Integridad IC-A/B + A5: **PROMOTE_PAPER**
- Revenue / live: **NO-GO** · **PROMOTE_LIVE: NO**
