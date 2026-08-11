# IC-WIRE + KPI SELL — refresh Día 7 (2026-08-11)

| Campo | Valor |
|-------|-------|
| Fecha | **2026-08-11T01:14Z** |
| Owner | `trader-market-maker` + desk-lead |
| Deadline DoD | **≤ 2026-08-13** |
| Modo | paper-only · sizing **200** · hash `630abf63…` · **PROMOTE_LIVE: NO** |
| Previo | `IC_SELL_STATUS_2026-08-09.md` · A5 PASS 08-10 |

## KPI SELL (runtime)

| Métrica | Corte 2026-08-11 (~01:14Z) | Umbral semanal (AC) | Estado |
|---------|----------------------------|---------------------|--------|
| Fills total | **350** | — | OK |
| BUY / SELL | **223 / 127** (~36% SELL) | SELL ≥ 10% fills **o** ≥1 SELL/24h | **ON_TRACK** |
| SELL/24h | **57** (BUY 58 / SELL 57) | ≥1 SELL/24h | **ON_TRACK** |
| Ciclos open / closed | **96 / 127** | ≥1 closed/día | **ON_TRACK** |
| Fees / realized net | ≈**3.54** / ≈**−7.03** | **no** edge claim | honesto / **NO-GO revenue** |
| Equity / ΔE₀ | ≈**976.2** / **−2.38%** | AT −1.5% / OFF −3% / PAUSE_GATE −5% | **AT_RISK** (digest) |

No bajar spacing / no subir sizing. MtM ≠ edge. SELL ON_TRACK **no** implica edge.

## IC-WIRE residual → 08-13

| Control | Estado 08-11 | Residual |
|---------|--------------|----------|
| IC-1 / IC-2 código + A5 | **DONE** #89 · A5 PASS | — |
| CB `system_integrity` | **activo** · *pérdidas consecutivas: 5* | AS-10 HOLD (no auto-clear) |
| IC-2 Redis shared en ops | Best-effort | OK mientras AS-10 no limpie PnL CB |
| DoD formal ≤08-13 | **PROMOTE_PAPER** integridad | Waiver solo si deadline slip |

**Veredicto Día 7:** KPI SELL **ON_TRACK** · capital **AT_RISK** · IC wire **GO paper**. Live: **NO**.

## Go / no-go
- Integridad IC + SELL: **PROMOTE_PAPER**
- Revenue / live: **NO-GO** · **PROMOTE_LIVE: NO**
