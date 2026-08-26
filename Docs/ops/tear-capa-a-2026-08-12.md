# Tear Capa A — 2026-08-12 UTC (auto EOD)

| Campo | Valor |
|-------|-------|
| Generado | 2026-08-12T00:45:02.566969+00:00 |
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
| **A4** | PASS c/nota | E_last=978.8946659324 MtM ≠ edge |
| **A5** | PASS | daily_close_at en 15/369 |
| **A6** | PASS | paper-only path |
| **A7** | FAIL | active=['system_integrity'] |
| **A8** | PASS | fills=350 fees=3.541994223 |

## Actividad / costos (honesto)

| Métrica | Valor |
|---------|-------|
| Fills | **350** (BUY 223 / SELL 127) |
| Fees USDT | 3.541994223 |
| Slippage USDT | 0.7083988446 |
| Cash | 22.3306659324 |
| Realized gross / net | -3.940707 / **-7.0277261868** |
| Equity MtM (último) | 978.8946659324 |
| Ciclos open / closed | 96 / 127 |
| Sharpe / Calmar / MaxDD | **N/A** (muestra / sin edge estable) |

**Lectura:** actividad y costos ≠ edge. Realized_net y MtM **no** son claim de rentabilidad.

## Go / no-go
- Integridad: **ITERATE**
- Revenue / live: **NO-GO**
- **PROMOTE_LIVE: NO**
