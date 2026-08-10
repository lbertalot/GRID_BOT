# IC-WIRE + KPI SELL — status paper L0 (AS-3)

| Campo | Valor |
|-------|-------|
| Fecha | **2026-08-09** |
| Owner | `trader-market-maker` + `trading-backend-tdd` |
| Deadline DoD | **≤ 2026-08-13** |
| Modo | paper-only · sizing **200** · hash `630abf63…` · **PROMOTE_LIVE: NO** |
| Spec | `GRID_BOT/Docs/L0_PAPER_FREEZE_PARAMS.md` §2.3 |

## KPI SELL (ventana)

| Métrica | Corte 2026-08-09 (~15:00Z) | Umbral semanal (AC) | Estado |
|---------|----------------------------|---------------------|--------|
| Fills total | 128 | — | OK actividad |
| BUY / SELL | **112 / 16** | SELL ≥ 10% de fills **o** ≥1 SELL/24h sostenido | **PARCIAL** (~12.5% SELL; sesgo BUY persiste) |
| Ciclos closed | 15 | ≥1 ciclo closed/día UTC | **ON_TRACK** (parcial vs fills) |
| Realized net | ≈0.072 USDT | **no** es edge claim | honesto / no-go revenue |
| Fees | ≈1.30 USDT | costos en tear | OK telemetría |

**Lectura:** hay SELL y ciclos cerrados (mejor vs 97B/2S del brief matutino), pero el book sigue BUY-heavy. No bajar spacing / no subir sizing.

## IC-WIRE progreso → 08-13

| Control | Estado 08-09 | Residual |
|---------|--------------|----------|
| IC-1 evento + gauge | Cableado | — |
| IC-1 gate BUY bajo piso | Cableado | Cancel-all BUY pendientes paper sim (backend, ≤08-11) |
| IC-2 evento + DD observe | Cableado | — |
| IC-2 flatten auto en ciclo | Stub API | Enganche ledger+marks Celery (MM+BE ≤08-12) |
| Simulacro desk A5 | Abierto | ≤08-20 (no bloquea gate E7 08-13) |

**Veredicto AS-3 hoy:** `IC_WIRE_STUB_ENFORCE` + SELL **PARCIAL** → seguir plan MM; gate E7 **no cerrado**.

## Plan MM (sin CEO Telegram)

1. Cada digest: si área MM AT_RISK → acción auto “chequear SELL/24h + IC-1/IC-2”.
2. ≤08-11: residual cancel-all BUY (backend-tdd).
3. ≤08-12: flatten IC-2 en ciclo paper.
4. ≤08-13: acta go/no-go E7 con evidencia logs+métricas; **no** live.

## Go / no-go
- Integridad paper: **ITERATE**
- IC DoD 08-13: **ABIERTO**
- Revenue / live: **NO-GO** · **PROMOTE_LIVE: NO**
