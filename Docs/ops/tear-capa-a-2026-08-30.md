# Tear Capa A — 2026-08-30 UTC (auto EOD)

| Campo | Valor |
|-------|-------|
| Generado | 2026-08-30T00:45:00.781931+00:00 |
| Modo | paper · **PROMOTE_LIVE: NO** |
| E_0 / deployed | 1000 / 200 |
| Hash | `ac1cb59676abbaa42a9e…` |
| SoT | `paper_telemetry/paper_equity_ledger.json` + series |

## Checklist A1–A8

| ID | Resultado | Nota |
|----|-----------|------|
| **A1** | PASS | hash `ac1cb59676abbaa4…` |
| **A2** | FAIL | gaps>2h count=3 |
| **A3** | PASS | effective_mode=paper |
| **A4** | PASS c/nota | E_last=999.0232991152 MtM ≠ edge |
| **A5** | PASS | daily_close_at en 11/203 |
| **A6** | PASS | paper-only path |
| **A7** | FAIL | active=['system_integrity'] |
| **A8** | PASS | fills=38 fees=0.763487404 |

## Actividad / costos (honesto)

| Métrica | Valor |
|---------|-------|
| Fills | **38** (BUY 19 / SELL 19) |
| Fees USDT | 0.763487404 |
| Slippage USDT | 0.1526974808 |
| Cash | 999.0232991152 |
| Realized gross / net | -0.060516 / **-0.9767008848** |
| Equity MtM (último) | 999.0232991152 |
| Ciclos open / closed | 0 / 19 |
| Sharpe / Calmar / MaxDD | **N/A** (muestra / sin edge estable) |

**Lectura:** actividad y costos ≠ edge. Realized_net y MtM **no** son claim de rentabilidad.

## Go / no-go
- Integridad: **ITERATE**
- Revenue / live: **NO-GO**
- **PROMOTE_LIVE: NO**
