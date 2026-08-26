# Tear Capa A — 2026-08-19 UTC (auto EOD)

| Campo | Valor |
|-------|-------|
| Generado | 2026-08-19T00:45:00.090257+00:00 |
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
| **A4** | PASS c/nota | E_last=999.847719272289545668178256 MtM ≠ edge |
| **A5** | PASS | daily_close_at en 25/421 |
| **A6** | PASS | paper-only path |
| **A7** | PASS | any_open=false |
| **A8** | PASS | fills=6 fees=0.09996472665052738606812 |

## Actividad / costos (honesto)

| Métrica | Valor |
|---------|-------|
| Fills | **6** (BUY 3 / SELL 3) |
| Fees USDT | 0.09996472665052738606812 |
| Slippage USDT | 0.019992945330105477213624 |
| Cash | 999.844688978546755687698256 |
| Realized gross / net | -0.03237845545321079814 / **-0.152332557561020380640688** |
| Equity MtM (último) | 999.847719272289545668178256 |
| Ciclos open / closed | 1 / 2 |
| Sharpe / Calmar / MaxDD | **N/A** (muestra / sin edge estable) |

**Lectura:** actividad y costos ≠ edge. Realized_net y MtM **no** son claim de rentabilidad.

## Go / no-go
- Integridad: **PROMOTE_PAPER**
- Revenue / live: **NO-GO**
- **PROMOTE_LIVE: NO**
