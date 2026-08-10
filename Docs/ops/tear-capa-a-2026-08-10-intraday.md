# Tear Capa A — 2026-08-10 UTC (intraday desk · post-CEO)

| Campo | Valor |
|-------|-------|
| Generado | 2026-08-10T19:06:01.403183+00:00 |
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
| **A4** | PASS c/nota | E_last=973.8889786932 MtM ≠ edge |
| **A5** | PASS | daily_close_at en 9/265 |
| **A6** | PASS | paper-only path |
| **A7** | PASS | any_open=false |
| **A8** | PASS | fills=350 fees=3.541447041 |

## Actividad / costos (honesto)

| Métrica | Valor |
|---------|-------|
| Fills | **350** (BUY 223 / SELL 127) |
| Fees USDT | 3.541447041 |
| Slippage USDT | 0.7082894082 |
| Cash | 22.3935845508 |
| Realized gross / net | -4.183167 / **-7.2698952348** |
| Equity MtM (último) | 973.8889786932 |
| Ciclos open / closed | 96 / 127 |
| Sharpe / Calmar / MaxDD | **N/A** (muestra / sin edge estable) |

**Lectura:** actividad y costos ≠ edge. Realized_net y MtM **no** son claim de rentabilidad.

## Go / no-go
- Integridad: **ITERATE**
- Revenue / live: **NO-GO**
- **PROMOTE_LIVE: NO**
