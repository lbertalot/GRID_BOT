# Tear Capa A — 2026-08-15 UTC (auto EOD)

| Campo | Valor |
|-------|-------|
| Generado | 2026-08-15T00:45:00.041601+00:00 |
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
| **A4** | PASS c/nota | E_last=999.9421735444 MtM ≠ edge |
| **A5** | PASS | daily_close_at en 10/56 |
| **A6** | PASS | paper-only path |
| **A7** | PASS | any_open=false |
| **A8** | PASS | fills=2 fees=0.019966213 |

## Actividad / costos (honesto)

| Métrica | Valor |
|---------|-------|
| Fills | **2** (BUY 1 / SELL 1) |
| Fees USDT | 0.019966213 |
| Slippage USDT | 0.0039932426 |
| Cash | 999.9421735444 |
| Realized gross / net | -0.033867 / **-0.0578264556** |
| Equity MtM (último) | 999.9421735444 |
| Ciclos open / closed | 0 / 1 |
| Sharpe / Calmar / MaxDD | **N/A** (muestra / sin edge estable) |

**Lectura:** actividad y costos ≠ edge. Realized_net y MtM **no** son claim de rentabilidad.

## Go / no-go
- Integridad: **PROMOTE_PAPER**
- Revenue / live: **NO-GO**
- **PROMOTE_LIVE: NO**
