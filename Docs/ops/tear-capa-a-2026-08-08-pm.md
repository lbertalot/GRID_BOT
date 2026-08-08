# Tear Capa A — 2026-08-08 PM (post P0 ops)

| Campo | Valor |
|-------|-------|
| Corte | ~2026-08-08T20:45Z · Día **3/30** paper L0 |
| E_0 | 1000 · hash `630abf63…` · sizing 200 |
| Modo | PAPER · **PROMOTE_LIVE: NO** |
| SoT | `paper_telemetry/paper_equity_ledger.json` |

## Checklist A1–A8 (resumen)

| ID | Resultado | Nota |
|----|-----------|------|
| A1 | **PASS** | hash freeze |
| A2 | **FAIL hist.** | gaps día 1 documentados; no reabrir |
| A3 | **PASS** | paper |
| A4 | **PASS c/nota** | equity digest ~1000.7–1002 MtM ≠ edge |
| A5 | **PARCIAL** | marks de cierre existen; ritual EOD sigue |
| A6 | **PASS** | sin live |
| A7 | **PASS post-reset** | `any_open=false` tras validate OK |
| A8 | **PASS** | fills 97 · fees≈0.984 · slip en ledger · **SELL≥1** |

## Actividad / costos (honesto)

| Métrica | Valor |
|---------|-------|
| Fills | **97** (BUY **96** / SELL **1**) |
| Fees USDT | ≈ **0.984** |
| Realized net | ≈ **0.0069** |
| Cash | ≈ **34.76** |
| LowDailyROI | muteado en paper (no usar como SoT) |
| Sharpe/Calmar/MaxDD | **N/A** |

**Lectura:** hay round-trip mínimo y costos. **No** hay edge ni camino a USD 6k. Sesgo BUY sigue dominante; hace falta serie de SELLs.

## Go/no-go
- Ops hoy: **ITERATE** OK tras reset+SELL.
- Revenue/live: **NO-GO**.
