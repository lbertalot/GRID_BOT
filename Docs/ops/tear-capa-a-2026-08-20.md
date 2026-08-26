# Tear Capa A — 2026-08-20 UTC (auto EOD)

| Campo | Valor |
|-------|-------|
| Generado | 2026-08-20T00:45:00.039980+00:00 |
| Modo | paper · **PROMOTE_LIVE: NO** |
| E_0 / deployed | 1000 / 200 |
| Hash | `630abf63e4ff9e3a8499…` |
| SoT | `paper_telemetry/paper_equity_ledger.json` + series |

## Checklist A1–A8

| ID | Resultado | Nota |
|----|-----------|------|
| **A1** | PASS | hash `630abf63e4ff9e3a…` |
| **A2** | PASS | sin gaps >2h en samples |
| **A3** | PASS | effective_mode=paper |
| **A4** | PASS c/nota | E_last=998.092482301055924482156368 MtM ≠ edge |
| **A5** | PASS | daily_close_at en 29/517 |
| **A6** | PASS | paper-only path |
| **A7** | PASS | any_open=false |
| **A8** | PASS | fills=119 fees=2.60943120755331990588636 |

## Actividad / costos (honesto)

| Métrica | Valor |
|---------|-------|
| Fills | **119** (BUY 60 / SELL 59) |
| Fees USDT | 2.60943120755331990588636 |
| Slippage USDT | 0.521886241510663981177272 |
| Cash | 974.711838104255924482156368 |
| Realized gross / net | 1.20242255331990836922 / **-1.900863775344075517843632** |
| Equity MtM (último) | 998.092482301055924482156368 |
| Ciclos open / closed | 1 / 59 |
| Sharpe / Calmar / MaxDD | **N/A** (muestra / sin edge estable) |

**Lectura:** actividad y costos ≠ edge. Realized_net y MtM **no** son claim de rentabilidad.

## Go / no-go
- Integridad: **PROMOTE_PAPER**
- Revenue / live: **NO-GO**
- **PROMOTE_LIVE: NO**
