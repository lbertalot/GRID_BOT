# Tear Capa A — 2026-08-24 UTC (auto EOD)

| Campo | Valor |
|-------|-------|
| Generado | 2026-08-24T00:45:00.781269+00:00 |
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
| **A4** | PASS c/nota | E_last=997.856400038655924482156368 MtM ≠ edge |
| **A5** | PASS | daily_close_at en 45/900 |
| **A6** | PASS | paper-only path |
| **A7** | FAIL | active=['system_integrity'] |
| **A8** | PASS | fills=130 fees=2.86585959555331990588636 |

## Actividad / costos (honesto)

| Métrica | Valor |
|---------|-------|
| Fills | **130** (BUY 65 / SELL 65) |
| Fees USDT | 2.86585959555331990588636 |
| Slippage USDT | 0.573171919110663981177272 |
| Cash | 997.856400038655924482156368 |
| Realized gross / net | 1.29543155331990836922 / **-2.143599961344075517843632** |
| Equity MtM (último) | 997.856400038655924482156368 |
| Ciclos open / closed | 0 / 65 |
| Sharpe / Calmar / MaxDD | **N/A** (muestra / sin edge estable) |

**Lectura:** actividad y costos ≠ edge. Realized_net y MtM **no** son claim de rentabilidad.

## Go / no-go
- Integridad: **ITERATE**
- Revenue / live: **NO-GO**
- **PROMOTE_LIVE: NO**
