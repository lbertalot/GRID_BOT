# Tear Sheet Paper 30d — Spec ejecutable (Core Grid L0-A)

- **Owner:** `trading-quant-engineer` (cómo se mide) · **Umbrales:** Desk Lead (`desk-policy-l0.md` §3 manda)
- **Book:** `core_grid` · Engine: GRID_BOT spot Binance · Modo: **paper only**
- **Ventana canónica:** 2026-08-15 00:00 UTC → 2026-09-14 00:00 UTC = **30 retornos diarios**
- **Denominador maestro:** capital **desplegado USD 200** (no `K_core` = 560)
- **Estado:** spec de medición alineada a desk-policy L0 v2. **No autoriza live.**
- **Skills:** `trading-pnl-tear-sheet` · `trading-backtest-promotion-gates`
- **Referencias:** [`desk-policy-l0.md`](../../Docs/squad/desk-policy-l0.md) §3 · [`tear-sheet-spec.md`](../../Docs/engineering/tear-sheet-spec.md) · `app/core/paper_equity_ledger.py` (S10)

> **Regla de oro:** toda métrica se calcula sobre equity mark-to-market  
> `E_t = cash_USDT + Σ_a (qty_a × mid_a)`, fees ya restadas del cash/inventario.  
> **Prohibido** gatear o reportar performance sobre `trades.profit_loss` (mentira mecánica del grid).

---

## 0. TL;DR del gate

Con 30 días y USD 200 desplegados **no se demuestra edge**. El tear sheet prueba integridad contable, estructura de costos y respeto de límites bajo carga. Cualquier redacción que diga "el paper demostró rentabilidad" se rechaza en la firma.

Veredictos permitidos al cerrar la ventana: **`ITERATE` | `PROMOTE_PAPER` | `REJECT`**.  
**Nunca** emitir `PROMOTE_LIVE` automático (regla `40-no-live-without-gate` + firma dual CEO + Desk Lead).

---

## 1. Checklist Capa A — integridad (go/no-go binario)

Un solo rojo **invalida el tear sheet completo**. No se compensa con PnL.

| # | Gate | Umbral / evidencia | Fuente de datos | Go | No-go |
|---|------|--------------------|-----------------|----|-------|
| **A1** | Config congelada | Un solo `config_hash` de punta a punta; cualquier cambio **reinicia la ventana** | `PaperEquitySeries.config_is_frozen()` / `config_hashes()` | ☐ | ☐ |
| **A2** | Cobertura de serie | ≥ **95%** snapshots esperados; **sin gaps > 2 h**; ≥ **30** cierres diarios 00:00 UTC | `PaperEquitySeries.coverage()` | ☐ | ☐ |
| **A3** | Reconciliación | `\|E_t − (cash_t + Σ qty·mid)\| / E_t ≤ 0,1%` en todo `t` | `equity_breakdown` vs marca registrada | ☐ | ☐ |
| **A4** | Identidad de PnL | `E_T − E_0 = Σ realizado + Δ no realizado − ops`, tol. ≤ 0,1% | Ledger + cierres diarios | ☐ | ☐ |
| **A5** | Fees atribuidas | 100% fills con `commission` / `commission_usdt` persistidos | `PaperFill` en ledger | ☐ | ☐ |
| **A6** | Precio de marcación real | Ticker Binance real; si falta precio → hueco (no inventar) | `MarkPriceUnavailable` / feed | ☐ | ☐ |
| **A7** | Disciplina de riesgo | 0 breaches daily −3%, kill o IC-2 que el breaker **no** haya cortado | Breakers + log de trips | ☐ | ☐ |
| **A8** | Sin live | `effective_mode = paper` en el 100% de las marcas; `FORCE_REAL_MODE` off | `trading_mode` snapshot | ☐ | ☐ |

### 1.1 Anti-métricas (no usar)

| Prohibido | Por qué |
|-----------|---------|
| `trades.profit_loss` / hit rate de ciclos como KPI | En grid todo ciclo cerrado es ganador por construcción; la pérdida vive en inventario MtM |
| Equity con balances fijos o BTC/ETH hardcodeados | Viola A6; serie ficticia |
| Promediar Capa A con Capa B | Un rojo en A invalida todo |

---

## 2. Umbrales Capa B — performance (ventana 30d, desplegado = 200)

Anualización de Sharpe: `√365`. Retornos diarios MtM, cierre 00:00 UTC.

| Métrica | Verde | Ámbar | Rojo / no-go | Equiv. USD (200) |
|---------|-------|-------|--------------|------------------|
| **PnL neto MtM** | ≥ **+0,7%** del desplegado | 0 ≤ PnL < 0,7% | **< 0** | ≥ **+1,40** / rojo si < 0 |
| **MaxDD MtM** (`maxdd_pct_deployed`) | ≤ **5,0%** | 5–10% | **> 10,0%** | ≤ 10 / > 20 |
| **Cobertura serie** (A2) | ≥ **95%** + ≥30 cierres + gap ≤ 2 h | — | incumplimiento | — |
| **`cost_ratio`** | ≤ 60% | 60–75% (audit si > 40% con spacing 100 bps) | **> 75%** | — |
| **Ciclos cerrados** | ≥ **120** y ≥ 30/semana × 4 | — | < 120 o semana < 30 | — |
| **Estabilidad semanal** | ≥ 3/4 semanas PnL ≥ 0; peor ≥ **−2,0%** | — | ≥2 semanas < 0 o peor < −2% | peor ≥ −4,00 |
| **Sharpe neto anual** | ≥ 0,5 (solo "no descartado") | — | **< 0,5** | publicar **siempre con IC95** |
| **Calmar de período** | ≥ 1,0 | 0,5–1,0 | **< 0,5** | `PnL_neto / MaxDD` (no anualizar) |
| **Hurdle rf** | PnL ≥ `200 × 4,5% × 30/365` | — | por debajo | ≥ **USD 0,74** |
| **`ratio_inventario`** | — | audit si **> 80%** | no gatea solo | — |
| **Haircut fill 0,70** | pasa **con y sin** haircut | solo sin haircut → **ámbar, nunca verde** | — | — |

### 2.1 Reporte dual de MaxDD (obligatorio)

| Campo | Denominador | ¿Gatea? |
|-------|-------------|---------|
| `maxdd_pct_deployed` | capital desplegado **200** | **Sí** |
| `maxdd_pct_book` | `K_core` 560 | No (CEO / book) |
| `dd_trading` | tradable (aportado − ops_committed) | No (CEO / kill) |

API del ledger: `PaperEquitySeries.max_drawdown_pct_deployed(deployed_capital=200)`.

### 2.2 No-go por resultado demasiado bueno (auditoría, no aprobación)

`SR_anual > 5` · `PnL_neto > 5%` del desplegado · `cost_ratio < 15%` · `MaxDD < 0,5%` · `ratio_frecuencia > 2,0` → **auditoría obligatoria** antes de firmar.

### 2.3 Config congelada de la ventana (desk §2.4)

| Parámetro | Valor |
|-----------|-------|
| Símbolo | ETHUSDT (alt. BTCUSDT) — **1 solo** |
| Desplegado | **USD 200** |
| Niveles | 10 (5/5) · USD 20/nivel |
| Spacing | **100 bps** · rango ±5% |
| Apalancamiento | 1× spot |
| Costo modelo | **24 bps** RT (10 fee + 2 selección adversa / lado) |

Cambio de cualquiera → nuevo `config_hash` → **reinicio de ventana** (A1 / N11).

---

## 3. Qué métricas faltan HOY (sin inventar P&L)

Estado al redactar esta spec. Donde no hay fuente confiable → **`unavailable` / nulo**, nunca cero fabricado ni P&L inventado.

| Artefacto / métrica | Estado hoy | Implicación |
|---------------------|------------|-------------|
| **`pnl_mtd` CEO dashboard** | Card **`unavailable`**: no existe `app.core.pnl_ledger` (ADR-004 PnL) | No usar el overview CEO como fuente del tear sheet 30d |
| **Serie equity paper 30d completa** | Código S10 (`PaperEquityLedger` / `PaperEquitySeries`) listo; **ventana canónica aún no arrancada** (freeze ≤ 2026-08-15) | Sin ticks + freeze no hay tear sheet firmable |
| **Export offline CSV/JSON de cierres diarios** | Gap I-15 del Quant: parcial (JSON de serie en `paper_telemetry/`) | Reproducibilidad por tercero incompleta |
| **Calmar / Sharpe IC95 en DB `performance_metrics`** | Columnas existen; poblado inconsistente / stubs | Calcular offline desde `PaperEquitySeries.daily_returns()` |
| **`pnl_economico = pnl_neto − ops_prorrateado`** | Ops ledger existe; **no cableado** al tear sheet automático | Línea manual separada en el reporte |
| **Haircut 0,70 medido** | Solo supuesto; sin contador de toques sin fill (I-16) | Reportar B1 con/sin haircut; no promover a verde solo sin haircut |
| **Capa A sobre datos en producción paper** | Tests unitarios S10 verdes; verificación A2/A3/A4 en runtime = acción abierta desk A3 | Bloqueante antes de firmar |
| **Simuladores legacy** | Deprecados documentalmente; SoT = ledger | Si algún path aún escribe equity distinto → invalidar serie |

### 3.1 Regla de honestidad

```
si falta serie MtM o cobertura < 95% → veredicto = ITERATE o REJECT
                                        (nunca inventar equity / PnL)
si pnl_mtd CEO = unavailable         → omitir del tear sheet; no rellenar
```

---

## 4. Alimentación desde `PaperEquityLedger` / `PaperEquitySeries`

### 4.1 Pipeline (paper)

```
fills grid (paper)
    → PaperEquityLedger.apply_fill / open-close cycle
         (fees + slippage restados del cash; cycle_id; realized gross/net)
    → compute_paper_portfolio_value()  [cada snapshot ~900 s]
         mark_to_market(ticker real)
         → PaperEquitySeries.record(E_t, cash, inventory, deployed, config_hash)
    → persistencia JSON:
         paper_telemetry/paper_equity_ledger.json
         paper_telemetry/paper_equity_series.json
    → tear sheet 30d (este documento)
```

Singleton: `get_paper_ledger()` · `get_paper_equity_series()`.  
Env: `PAPER_TELEMETRY_DIR` (default `paper_telemetry`), `PAPER_INITIAL_CASH_USDT`.

### 4.2 Mapeo métrica → API

| Métrica tear sheet | Método / campo |
|--------------------|----------------|
| Equity MtM `E_t` | `ledger.mark_to_market(prices)` / `equity_breakdown` |
| PnL neto ventana | `E_T − E_0` sobre cierres diarios (no `trades.profit_loss`) |
| Cierres / `r_t` | `series.daily_closes()` · `series.daily_returns()` |
| MaxDD % desplegado | `series.max_drawdown_pct_deployed(200)` |
| MaxDD USD | `series.max_drawdown_usdt()` |
| Cobertura / gaps | `series.coverage()` → `samples`, `max_gap_seconds`, `daily_closes` |
| Config freeze (A1) | `series.config_is_frozen()` |
| `cost_ratio` | `ledger.cost_ratio()` |
| `ratio_inventario` | `ledger.inventory_ratio(prices)` |
| Ciclos cerrados | ciclos con buy+sell emparejados (`cycle_id` / `GridCycle` cerrados) |
| Fees | `PaperFill.commission_usdt` · totales en `to_dict()` |

### 4.3 Procedimiento ejecutable al cierre de ventana

1. Confirmar `effective_mode=paper` y A8 en logs del período.
2. Cargar `paper_equity_series.json` + `paper_equity_ledger.json` del entorno paper.
3. Filtrar samples al intervalo canónico `[T0, T1)`.
4. Evaluar **Capa A** en orden A1→A8; si algún rojo → `REJECT` o `ITERATE` (reinicio), stop.
5. Calcular Capa B con denominador **200**; publicar dual MaxDD.
6. Reportar B1 **con y sin** haircut 0,70.
7. Completar plantilla §5 y emitir **un** veredicto de §6.
8. No pegar números del CEO overview si `pnl_mtd.status=unavailable`.

---

## 5. Plantilla de salida (español)

```text
## Tear sheet Core Grid — paper 30d
Ventana: <T0> → <T1> UTC | config_hash: <h> | desplegado: USD 200
Modo: paper | Símbolo: <ETHUSDT|BTCUSDT>

### Capa A
A1..A8: GO / NO-GO (detalle)

### Capa B (netos de costos)
PnL_neto MtM: <usd> (<pct>% desplegado) | con haircut 0.70: <...>
MaxDD: <pct_deployed>% (gate) | <pct_book>% | dd_trading: <...>
cost_ratio: <...> | ciclos: <n> (semanas: ...)
Sharpe anual (IC95): <...> | Calmar período: <...>
ratio_inventario: <...> | hurdle rf: <pass|fail>

### Limitaciones
- Muestra 30d: no prueba edge estadístico.
- Métricas unavailable: <lista honesta>

### Veredicto
ITERATE | PROMOTE_PAPER | REJECT
(Justificación 3–5 líneas. PROMOTE_LIVE = prohibido aquí.)
```

---

## 6. Veredictos

| Veredicto | Cuándo | Siguiente paso |
|-----------|--------|----------------|
| **`REJECT`** | Cualquier no-go de desk §3.4 (Capa A roja, PnL < 0, MaxDD > 10%, cost_ratio > 75%, ciclos insuficientes, Sharpe < 0,5, Calmar < 0,5, orden real en paper, etc.) | Postmortem; no firmar gate; replanificar ventana o hipótesis |
| **`ITERATE`** | Capa A incompleta / cobertura < 95% / instrumentación a medias / ámbar frágil (pasa solo sin haircut) / métricas críticas `unavailable` | Extender o reiniciar ventana; **no** relajar umbrales post-datos |
| **`PROMOTE_PAPER`** | Capa A toda verde **y** Capa B sin rojo **y** sin disparadores de auditoría abiertos | Mantener paper; habilita conversación de rampa **solo** con firma humana posterior. **No es live.** |
| **`PROMOTE_LIVE`** | **No existe en este artefacto** | Requiere firma dual CEO + Desk Lead (RFC-004 / ADR-007) + checklist regla 40 |

### 6.1 Relación con skills

- `trading-pnl-tear-sheet`: formato ejecutivo + métricas netas + veredicto tri-estado.
- `trading-backtest-promotion-gates`: research→event-driven→paper; **nunca** `PROMOTE_LIVE` sin confirmación humana explícita.

---

## 7. Changelog

| Fecha | Cambio | Autor |
|-------|--------|-------|
| 2026-08-05 | Spec ejecutable 30d: Capa A/B alineada desk-policy L0 v2; denominador desplegado 200; feed PaperEquityLedger; gaps honestos (`pnl_mtd` unavailable); veredictos sin PROMOTE_LIVE | Quant |

> Los umbrales **no se relajan después de ver los datos**. Corrección solo *antes* de la ventana siguiente, con justificación firmada aquí.
