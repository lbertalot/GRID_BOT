# Tear Capa A — 2026-08-09 UTC (auto EOD)

| Campo | Valor |
|-------|-------|
| Generado | 2026-08-09T15:00:00+00:00 |
| Modo | paper · **PROMOTE_LIVE: NO** |
| E_0 / deployed | 1000 / 200 |
| Hash | `630abf63e4ff9e3a8499…` |
| SoT | `paper_telemetry/paper_equity_ledger.json` + series |

## Checklist A1–A8

| ID | Resultado | Nota |
|----|-----------|------|
| **A1** | PASS | hash `630abf63e4ff9e3a…` |
| **A2** | FAIL | gaps>2h count=2 |
| **A3** | PASS | effective_mode=paper |
| **A4** | PASS c/nota | E_last=1002.4382735444 MtM ≠ edge |
| **A5** | PASS | daily_close_at en 8/210 |
| **A6** | PASS | paper-only path |
| **A7** | PASS | any_open=false |
| **A8** | PASS | fills=128 fees=1.297846826 |

## Actividad / costos (honesto)

| Métrica | Valor |
|---------|-------|
| Fills | **128** (BUY 112 / SELL 16) |
| Fees USDT | 1.297846826 |
| Slippage USDT | 0.2595693652 |
| Cash | 24.7923218088 |
| Realized gross / net | 0.460251 / **0.0717674244** |
| Equity MtM (último) | 1002.4382735444 |
| Ciclos open / closed | 97 / 15 |
| Sharpe / Calmar / MaxDD | **N/A** (muestra / sin edge estable) |

**Lectura:** actividad y costos ≠ edge. Realized_net y MtM **no** son claim de rentabilidad.

## Go / no-go
- Integridad: **ITERATE**
- Revenue / live: **NO-GO**
- **PROMOTE_LIVE: NO**
