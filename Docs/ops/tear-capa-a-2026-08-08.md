# Tear Capa A — 2026-08-08 UTC (ventana L0)

| Campo | Valor |
|-------|-------|
| Ventana | paper L0 · ~Día **3/30** · ancla `2026-08-06` |
| E_0 | 1000 USDT · hash freeze `630abf63…` |
| Modo | PAPER · **PROMOTE_LIVE: NO** · sizing 200 |
| SoT | `paper_telemetry/paper_equity_ledger.json` + series |
| Owner | quant + desk/EM (corte ~14:10Z) |

---

## Checklist A1–A8

| ID | Check | Resultado | Nota |
|----|-------|-----------|------|
| **A1** | `config_hash` = freeze | **PASS** | homogéneo `630abf63…` en series |
| **A2** | Gaps serie ≤2h | **FAIL** | 2 gaps históricos (2.15h; ~19h 06→07). Sin gap nuevo evidente en tramo fills |
| **A3** | `effective_mode=paper` | **PASS** | stack paper |
| **A4** | Equity SoT coherente | **PASS c/nota** | equity serie min/max ≈998.8–1001.5; **no** interpretarlo como edge |
| **A5** | Cierre diario ±30m 00:00Z | **PARCIAL** | series reporta marks `daily_close_at` (n=3); ritual EOD sigue en ventana 23:30–00:30Z |
| **A6** | Sin live / FORCE vacío | **PASS** | |
| **A7** | Breakers / integridad | **PASS post-ops** | IP egress `148.222…`; reset `system_integrity` stale OK; `any_open=false` al corte |
| **A8** | Costos / fills honestos | **PASS** | fills **82** (BUY 81 / **SELL 1**) · fees≈**0.833** · slip≈**0.167** · realized_net≈**0.008** |

---

## Actividad / costos (honesto)

| Métrica | Valor |
|---------|-------|
| Fills (acum. ledger) | 82 |
| Mix | BUY 81 · SELL **1** (primer round-trip tras fix last_action) |
| Fees total USDT | ≈ 0.833 |
| Slippage total USDT | ≈ 0.167 |
| Cash paper | ≈ 186.85 |
| Realized gross / net | ≈ 0.033 / **0.008** |
| Equity serie (último sample) | ≈ 1000.83 (MtM; puede lag vs ledger post-SELL) |
| Sharpe / Calmar / MaxDD | **N/A** — muestra insuficiente / sin edge estable |

**Lectura producto:** hay **actividad y costos reales en paper**. Realized_net≈0.008 **no** es edge ni camino a USD 6k. El sesgo BUY se corrigió en código (RCA `rca-buy-only-last-action-2026-08-08.md`); falta **serie de SELLs** y tear multi-día.

---

## Go / no-go

- Integridad operativa hoy: **ITERATE** (A2 histórico en rojo; A5 parcial).
- Estrategia / revenue: **NO-GO** claim de rentabilidad.
- **PROMOTE_LIVE: NO**.

## Acciones siguientes
1. Dejar correr paper y acumular SELL (vigilar IC / cash).
2. Cierre formal en ventana 23:30–00:30Z.
3. Tear diario con fees hasta que haya ≥N round-trips.
