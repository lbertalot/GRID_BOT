# Tear sheet Core Grid — paper 30d (Fase 0, no firmado)

Ventana canónica: **2026-08-15 00:00 UTC → 2026-09-14 00:00 UTC** | desplegado: **USD 200**  
Corte de evidencia: **2026-09-10T13:22:50Z** (día 27/30 de serie runtime; día 28/30 de calendario N10)  
Modo: **paper** | Símbolo: **ETHUSDT** | **PROMOTE_LIVE: NO**

SoT: `paper_telemetry/paper_equity_ledger.json` + `paper_equity_series.json`.  
**No** se usó `trades.profit_loss`. **No** se usó `pnl_mtd` CEO (`unavailable`).  
Prueba SI 5×15 intento 3 (`t0=2026-09-09T18:01:46Z`): **0** closes `closed_at > t0` — **excluida** de los KPI de esta ventana (ver [trial §8](trial-si-5x15-2026-09-09.md)).

Hashes (no mezclar):

| Origen | Hash |
|--------|------|
| Serie / samples (n=501, único) | `ac1cb59676abbaa42a9e1409809ee3b7009ae5114e15055615a7a1ff63b4b219` |
| Sidecar N10 (`grid_config_paper_l0.hash`) | `ff6a35fcf84bf91c1da9ea81116265a3789f1d85e5456d19622897c82ed7f5c4` |
| Overlay trial 5×15 (cerrado, no en serie) | `6c03b776d09f5a8c952d530448f3182120359ab3bb1794be1ee16890d62cbae7` |

---

## Capa A (spec TEAR_SHEET_PAPER_30D.md §1)

Evaluación **manual** sobre SoT (el auto-tear histórico mapeaba mal A1/A3/A5/A8; el renderer se alineó al spec el 2026-09-10).

| ID | Resultado | Nota |
|----|-----------|------|
| **A1** | **FAIL / deuda** | Serie internamente un hash (`ac1cb596…`) pero **≠** sidecar N10 `ff6a35fc…`. MM OFF_TRACK = last≠expected. Un solo hash en samples (no drift intra-serie). |
| **A2** | **FAIL** | `gaps>2h count=13` · `max_gap≈126.1 h` · samples desde 2026-08-26 (faltan ~11 d del T0 08-15) · daily_close_at **24** (hace falta ≥30) |
| **A3** | **PASS** | E_last 999.0232991152 = cash 999.0232991152 + inv 0 · error 0% ≤0,1% |
| **A4** | **PASS c/nota** | E_T − E_0 = −0.9767008848 = realized_net. MtM ≠ edge |
| **A5** | **PASS** | 38/38 fills con campo fee · fees 0.763487404 · slippage 0.1526974808 |
| **A6** | **PASS** | path paper; inventory 0 (sin marca inventada en último sample) |
| **A7** | **PASS c/nota** | SI OPEN es el corte del NO-GO 5×15, no un breach −3% sin breaker |
| **A8** | **PASS** | `effective_mode=paper` · `force_real_mode=false` en `/health` todo el muestreo |

Un rojo de Capa A **invalida** el tear completo. A2 (y la deuda A1 vs sidecar) → no hay `PROMOTE_PAPER`.

---

## Capa B (netos de costos, denominador 200)

| Métrica | Valor | Semáforo |
|---------|-------|----------|
| PnL neto MtM | **−0.9767008848** USDT (−0.488% desplegado) | **ROJO** (&lt; 0) |
| con haircut 0.70 | `unavailable` (sin contador toques-sin-fill) | no verde |
| MaxDD `maxdd_pct_deployed` | **0.488%** (USD 0.9767) | verde numérico ≤5% |
| MaxDD `maxdd_pct_book` / `dd_trading` | N/A (K_core 560 no gatea) | — |
| `cost_ratio` | **`unavailable`** (`realized_gross` −0.060516 ≤ 0; API `cost_ratio()` retorna None) | no verde |
| Ciclos cerrados | **19** (0 open) · semanal ≪ 30 | **ROJO** (&lt; 120) |
| Estabilidad semanal | 3 semanas con daily_close, Δ equity **0** (todo post 26-ago plano en 999.02) | no 3/4 semanas positivas de PnL de trading |
| Sharpe anual (IC95) | **N/A** | retornos diarios ≈ 0; &lt;30 r_t independientes; no fabricar IC |
| Calmar período | **−1.0** (−0.9767 / 0.9767) | **ROJO** (&lt; 0,5) |
| Hurdle rf | 200 × 4,5% × 30/365 ≈ **0.74** USDT · PnL −0.98 | **FAIL** |
| `ratio_inventario` | **0** (último sample) / `unavailable` vs bruto ≤0 | — |

### Anti-métricas (no usadas)

- `trades.profit_loss` / hit rate de ciclos.
- ROI ops Binance histórico.
- Dashboard CEO `pnl_mtd`.

---

## Limitaciones

- Muestra 30d incompleta: serie arranca **2026-08-26**, no 08-15.
- 13 gaps &gt;2 h (A2 rojo).
- 19 ciclos, todos el 26-ago; idle de grid desde entonces (SI / HOLD).
- Overlay 5×15 no aportó closes; no se mezcla.
- Sharpe/Calmar/cost_ratio honestamente N/A o rojo.
- Hash de serie `ac1cb596…` es el freeze pre-qty-fix; sidecar N10 es `ff6a35fc…`.

---

## Veredicto (propuesta a firmar el 2026-09-14)

**ITERATE** (Capa A incompleta / A2 rojo / instrumentación de hash vs sidecar / muestra insuficiente).  
`REJECT` es defendible si Desk trata A2+PnL&lt;0 como no-go duro de §6.  
**No** `PROMOTE_PAPER`. **PROMOTE_LIVE: NO.**

Justificación: el paper no demuestra edge. Equity MtM bajó 0.98 USDT, casi todo fees+slippage sobre 19 ciclos del 26-ago. Cobertura y frecuencia no cumplen el gate. La prueba 5×15 no produjo closes nuevos.

Siguiente paso: Fase 1 ([fase1-action-plan-2026-09-15.md](fase1-action-plan-2026-09-15.md)) — una config candidata congelada, Capa A medible, sin optimizar in-sample.
