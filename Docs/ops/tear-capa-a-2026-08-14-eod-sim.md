# Tear Capa A — 2026-08-14 UTC (auto EOD)

| Campo | Valor |
|-------|-------|
| Generado | 2026-08-14T18:20:12.677193+00:00 |
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
| **A4** | PASS c/nota | E_last=999.940935952 MtM ≠ edge |
| **A5** | PASS | daily_close_at en 5/31 |
| **A6** | PASS | paper-only path |
| **A7** | PASS | any_open=false |
| **A8** | PASS | fills=1 fees=0.01000004 |

## Actividad / costos (honesto)

| Métrica | Valor |
|---------|-------|
| Fills | **1** (BUY 1 / SELL 0) |
| Fees USDT | 0.01000004 |
| Slippage USDT | 0.002000008 |
| Cash | 989.987959952 |
| Realized gross / net | 0 / **0** |
| Equity MtM (último) | 999.940935952 |
| Ciclos open / closed | 1 / 0 |
| Sharpe / Calmar / MaxDD | **N/A** (muestra / sin edge estable) |

**Lectura:** actividad y costos ≠ edge. Realized_net y MtM **no** son claim de rentabilidad.

## Go / no-go
- Integridad: **PROMOTE_PAPER**
- Revenue / live: **NO-GO**
- **PROMOTE_LIVE: NO**
