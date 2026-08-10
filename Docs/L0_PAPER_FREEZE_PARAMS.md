# L0 — Parámetros freeze paper + DoD primer tick

| Campo | Valor |
|-------|--------|
| **Owner** | `trader-market-maker` (book `core_grid`) |
| **Política** | monorepo `Docs/squad/desk-policy-l0.md` v2 §2 / §3 |
| **Código** | `app/core/paper_equity_ledger.py`, `grid_config_paper_l0.json`, `scripts/freeze_paper_l0_config.py` |
| **Skills** | `trading-risk-capital-preservation`, `trading-execution-layer`, `trading-pnl-tear-sheet` |
| **Modo** | **Paper-only.** No autoriza live. Prohibido `FORCE_REAL_MODE` / órdenes reales. |
| **Complementa** | `Docs/PAPER_WINDOW_DAY0.md` (runbook operativo día 0) |

Este documento **congela los números** que el desk exige para declarar válida la ventana paper L0-A. Cualquier cambio de parámetros de §1 tras el freeze reinicia el reloj (gate A1 / N11).

---

## 1. Config congelada — spacing, costos, notional

### 1.1 Grid L0-A (desk §2.4)

| Parámetro | Valor freeze | Notas |
|-----------|--------------|--------|
| Símbolo | **ETHUSDT** (único activo) | BTCUSDT inactivo |
| Capital desplegado | **USD 200** | Denominador MaxDD / IC-2; no el cap del book (560) |
| Composición | ~100 USDT + ~100 en base | Inventario inicial acotado al desplegado |
| Niveles | **10** (5 compra / 5 venta) | |
| Notional por nivel | **USD 20** | Piso duro **USD 15** (MIN_NOTIONAL × 1,5) |
| Spacing | **100 bps** (1,00%) | Rechazo si &lt; 40 bps |
| Rango | **±5%** del mid de freeze | IC-1 ancla al borde inferior |
| Apalancamiento | **1× spot** | |
| Modo | `PAPER` · `paper_only=true` · `force_real_mode=false` | |

**Cómo fijar mid / hash (día 0):**

```bash
python3.11 scripts/freeze_paper_l0_config.py --mid <PRECIO_SPOT_ETHUSDT>
python3.11 scripts/freeze_paper_l0_config.py --mid <PRECIO_SPOT_ETHUSDT> --write
cat grid_config_paper_l0.hash   # SHA-256 hex, 64 chars
```

Tras `--write`: `grid_config_paper_l0.json` pasa a `PAPER_FROZEN` y el sidecar `grid_config_paper_l0.hash` es la firma A1.

### 1.2 Modelo de costos — 24 bps round-trip (desk §2.1)

Adoptado de `tear-sheet-spec` / `PaperCostModel`. **Sin descuento BNB** (exposición direccional no deseada).

| Componente | bps / lado | Round-trip |
|------------|------------|------------|
| Fee maker (VIP0) | 10 | 20 |
| Selección adversa (supuesto declarado) | 2 | 4 |
| Spread cruzado (limits) | 0 | 0 |
| **Total** | **12** | **24 bps** |

En el ledger: fee → `commission` / `fees_total_usdt`; selección adversa → `slippage_usdt` / `slippage_total_usdt`. Ambos **se restan del cash** en cada fill (gates I-5 / I-6 / A5).

### 1.3 Economía por ciclo (notional USD 20)

| Concepto | Cálculo | USD |
|----------|---------|-----|
| Bruto (spacing 100 bps) | 20 × 1,00% | **0,200** |
| Costo RT 24 bps | 20 × 0,24% | **0,048** |
| Neto esperado | 76 bps captura | **0,152** |
| `cost_ratio` esperado | 24 / 100 | **24%** (verde ≤ 60%; auditoría si &gt; 40%) |

Proyección de volumen (desk §2.2, vol ETH ~3%/día): ≈ 4,5 ciclos/día → ~135 en 30 días (piso desk ≥ 120). **Si la proyección cae bajo 120: extender ventana, no bajar spacing.**

### 1.4 Inventario y riesgo (skill capital-preservation)

| Límite | Valor | Disparo |
|--------|-------|---------|
| Inventario máx. (diseño) | ≤ USD 240 → **desplegado 200** | Shock 10% no debe solo por sí disparar daily −3% del pool |
| MaxDD verde / rojo | ≤ **5%** / &gt; **10%** del desplegado | USD 10 / USD 20 |
| Daily flat (pool) | −3% equity tradable | Flat 24 h (RFC-002) |
| Kill | `dd_trading` ≤ −25% | Emergency stop (no aplica “día 0 válido”; sí A7 en ventana) |

---

## 2. IC-1 / IC-2 — qué debe pasar en paper

Controles de desk §2.5. Sin ellos el MaxDD ≤ 10% del desplegado **no es alcanzable por diseño** ante un movimiento adverso ordinario de ETH (~8–12% en 30 días). En paper deben **ejercitarse y medirse**, no solo documentarse.

### 2.1 IC-1 — Freno de carga fuera de rango

| | |
|--|--|
| **Regla** | Si el mid cae **por debajo del nivel de compra más bajo** (borde −5% del centro de freeze), el grid **deja de reponer compras** hasta que el precio vuelva al rango. |
| **Efecto** | Inventario acotado en ≈ USD 200; pérdida adicional = MtM del inventario ya cargado, no compra nueva “a cuchillo”. |
| **Paper — debe pasar** | (1) Flag/evento `IC1_stop_rebuy_outside_range` observable en logs/métricas. (2) Cero fills BUY nuevos en niveles fuera de rango mientras IC-1 activo. (3) Órdenes BUY pendientes fuera de rango canceladas o no re-posteadas. (4) Al volver al rango, reposición solo con breaker cerrado y reconciliación OK. |
| **Paper — no-go** | Rebuys continuos bajo el piso −5% · inventario paper &gt; desplegado por compras nuevas fuera de rango. |

Metadata freeze (`grid_config_paper_l0.json`): `ic_controls.IC1_stop_rebuy_outside_range = true`.

### 2.2 IC-2 — Corte de inventario del book Core

| | |
|--|--|
| **Regla** | Si el MtM del book Core alcanza **−10,0% del capital desplegado** (**−USD 20** con 200), se **aplana el book Core** (no el pool, no satellites). |
| **Alineación** | Mismo número que el rojo de aceptación MaxDD (§3.3): el criterio que rechaza en paper es el que corta en live. |
| **Independiente de** | Daily −3% del pool (sigue vigente y por encima). |
| **Paper — debe pasar** | (1) Al cruzar −10% desplegado: cancel-all Core + flatten inventario paper. (2) Evento `IC2` / métrica Prometheus + registro en tear sheet. (3) Gate A7: cero breaches de IC-2 **que el breaker no haya cortado**. (4) Tras IC-2: no re-armar sin diagnóstico escrito (mín. 30 min en runbook §5.3). |
| **Paper — no-go** | Equity Core &lt; −10% desplegado sin flatten · re-armado inmediato “para no perder fills”. |

Metadata: `ic_controls.IC2_flatten_core_at_deployed_dd_pct = "10.00"`.

### 2.3 Estado IC-WIRE (E7) — sprint S-WAVE-E-OBS

| Campo | Valor |
|-------|--------|
| **Slice** | E7 IC-WIRE · owner `trader-market-maker` · apoyo `trading-backend-tdd` |
| **Deadline** | **≤ 2026-08-13** (desk A2) |
| **Modo** | Paper-only · sizing desplegado **200** inmutable · **PROMOTE_LIVE=NO** |
| **Código** | `app/core/inventory_controls.py` · gate BUY en `OptimizedGridManager._execute_trade` · observe en `PaperTradingEngine.mark_to_market` |
| **Tests** | `tests/test_inventory_controls_ic_wire.py` (TDD) |
| **Métricas** | `ic1_stop_rebuy_active`, `ic2_flatten_active`, `ic1_trips_total`, `ic2_trips_total` |
| **ADR** | `Docs/ADR_IC_WIRE_E7.md` |

| Control | Runtime (2026-08-10 AS-3) | Residual → fecha |
|---------|---------------------------|------------------|
| **IC-1** evento `IC1_stop_rebuy_outside_range` | **Cableado** (observe + log + gauge) | — |
| **IC-1** gate BUY / no re-post bajo piso | **Cableado** (`allows_core_buy` en `_execute_trade`) | — |
| **IC-1** cancel-all BUY paper sim | **Cableado** (`paper_pending_orders` + trip) | Grid debe `add_buy` al postear resting · MM |
| **IC-2** evento + DD ≥ 10% desplegado | **Cableado** (peak serie / observe) | — |
| **IC-2** flatten inventario paper | **Cableado** (`mark_to_market` → `maybe_flatten_open_inventory_paper`) | Simulacro A5 evidencia ≤ 2026-08-20 |
| **IC-2** breaker `system_integrity` | Best-effort sync/async en enforce | Validar shared Redis en ops |
| Simulacro desk A5 (forzar mid/MtM) | Abierto | MM+devops **≤ 2026-08-20** (no bloquea E7 gate 08-13) |

**Veredicto 2026-08-10:** `IC_WIRE_ENFORCE` — cancel BUY + flatten E2E paper cableados; simulacro A5 = residual. **No** reinicia ventana (hash freeze intacto).

### 2.4 Simulacro (desk A5, deadline ~2026-08-20)

Antes de firmar la ventana completa (no bloquea el primer tick, sí A7 de la ventana):

1. Forzar precio paper bajo el piso −5% → verificar IC-1.
2. Forzar MtM Core a −10% desplegado → verificar IC-2 + flatten.
3. Documentar evidencia (logs + métricas) en el expediente del tear sheet.

---

## 3. DoD — primer tick paper válido

Un **tick** = un ciclo de marcación + (opcional) fills paper que dejan evidencia contable en `PaperEquityLedger` / `PaperEquitySeries` (S10). El primer tick válido es el que abre el conteo hacia el **día 0 de ventana**, no un smoke de health HTTP.

### 3.1 Precondiciones (todas)

- [ ] `effective_mode = paper` (100% marcas; gate A8).
- [ ] `FORCE_REAL_MODE` vacío; `PAPER_TRADING=true`; sin keys de prod.
- [ ] Config freeze ejecutado: `mid_price_at_freeze`, `min_price`, `max_price`, `quantity` no nulos; status `PAPER_FROZEN`.
- [ ] `config_hash` = contenido de `grid_config_paper_l0.hash` (64 hex) **o** `GRID_CONFIG_HASH` explícito igual al hash del archivo.
- [ ] Feed de marcación = ticker real Binance (gate A6). Si no hay precio → `MarkPriceUnavailable`; **no** inventar mid.
- [ ] Ledger inicializado con `deployed_capital = 200` (Decimal) y `PaperCostModel` 10+2 bps/lado.
- [ ] IC-1 / IC-2 flags presentes en metadata de config.

### 3.2 Qué se escribe en `PaperEquityLedger`

Por cada fill paper del tick (si hubo ejecución):

| Campo | Requisito |
|-------|-----------|
| `fill_id` | Persistido |
| `cycle_id` (I-8) | BUY abre ciclo; SELL cierra FIFO; bloqueante para conteo de ciclos |
| `symbol` / `side` / `quantity` / `price` | Decimal; filtros LOT/PRICE/MIN_NOTIONAL respetados |
| `notional_usdt` | `qty × price` |
| `commission` + `commission_usdt` | Fee atribuida (A5); descontada del cash |
| `slippage_usdt` | 2 bps selección adversa; descontada del cash |
| `executed_at` | UTC |

Estado del ledger tras el tick (siempre, haya o no fills):

| Campo | Requisito |
|-------|-----------|
| `cash` | Post-fees/slippage |
| `deployed_capital` | `"200"` (o Decimal 200) |
| `fees_total_usdt` / `slippage_total_usdt` | Acumulados; si hubo RT, coherentes con 24 bps |
| `cycles[]` / `fills[]` | JSON versionado (`schema_version: 1`) |
| Identidad A4 | `E_t − E_0 = pnl_neto_realizado + Δ no realizado` (tolerancia ≤ 0,1% en reconciliación A3) |

Equity MtM:

```
E_t = cash_USDT + Σ qty_a × mid_a   # fees ya en cash; mid de ticker real
```

### 3.3 Qué se escribe en `PaperEquitySeries` (marca del tick)

| Campo sample | Requisito primer tick válido |
|--------------|------------------------------|
| `at` | Timestamp UTC del snapshot |
| `equity` | String Decimal de `E_t` |
| `cash` / `inventory_value` | Presentes (permite A3) |
| `deployed_capital` | `"200"` |
| **`config_hash`** | **Idéntico** al hash congelado; un solo valor en toda la serie (A1) |
| `daily_close_at` | Si `|at − 00:00 UTC| ≤ 30 min` → ancla de cierre diario (I-13); el **día 0** exige al menos un cierre anclado o el primer cierre de la medianoche siguiente contable |

### 3.4 Checklist DoD — primer tick (binario)

| # | Criterio | Go si… |
|---|----------|--------|
| T1 | Modo paper | `effective_mode=paper`; cero órdenes reales |
| T2 | Hash | Sample lleva `config_hash` = sidecar freeze |
| T3 | Marcación real | Mid de ticker; sin hardcode |
| T4 | Fees | Todo fill con `commission` persistida y restada del cash |
| T5 | Costos modelo | `PaperCostModel.round_trip_bps == 24` |
| T6 | Desplegado | `deployed_capital == 200` en ledger y sample |
| T7 | Persistencia | Ledger + serie guardados (JSON atómico / path configurado) |
| T8 | Reconciliación | `\|E − (cash + Σ qty·mid)\| / E ≤ 0,1%` |
| T9 | Breakers | Ningún breaker abierto sin cancel-all; IC-1/IC-2 no en estado inconsistente |
| T10 | Decimal | Sin float monetario en path de ledger |

**Un solo rojo → tick inválido.** No cuenta para el arranque de ventana.

---

## 4. Go / no-go — “día 0 de ventana” válido

El **día 0** es el primer día calendario UTC cuya serie de equity paper es **contable y congelada**, y a partir del cual se cuentan los 30 retornos diarios de la ventana canónica (ideal: arranque ≤ 2026-08-15 00:00 UTC → cierre 2026-09-14).

### 4.1 GO — declarar día 0 válido

Todas las condiciones:

1. **Freeze A1 cerrado:** un único `config_hash` registrado; archivo `PAPER_FROZEN`; sin edits posteriores.
2. **≥ 1 primer tick válido** (§3) persistido con ese hash.
3. **Cierre diario 00:00 UTC** (o marca dentro de ±30 min) con `E_0` de referencia para retornos.
4. **Capa A preliminar en verde local:** A1, A6, A8; A3/A5 verificables sobre las marcas del día; A2 aún no aplica (cobertura de 30 días).
5. **IC-1 / IC-2** cableados o, como mínimo, flags freeze activos + owner A2 desk con fecha (implementación desk A2 ≤ 2026-08-13); sin rebuys fuera de rango en el día 0.
6. **Stack paper-safe:** compose / env según `PAPER_WINDOW_DAY0.md`; observabilidad up.
7. **Acta desk:** veredicto `L0_DAY0_WINDOW_GO` firmado por Desk Lead + market-maker (registro del hash + `E_0` + timestamp UTC).

Fórmula de calendario (desk §6):

```
go_live_candidate = inicio_ventana_limpia + 31 días
```

(Contingencia 2026-09-22 si el arranque se atrasa; **no** relajar 30 días ni 120 ciclos.)

### 4.2 NO-GO — no declarar día 0

Cualquiera:

| # | Condición |
|---|-----------|
| N1 | `config_hash` ausente, múltiple, o distinto del sidecar |
| N2 | Tick con mid inventado / feed caído forzado a constante |
| N3 | Fills sin `commission` o fees no descontadas del cash |
| N4 | `deployed_capital` ≠ 200 o spacing / niveles ≠ freeze §1 |
| N5 | `effective_mode ≠ paper` o cualquier orden real |
| N6 | Reconciliación A3 &gt; 0,1% sin causa raíz cerrada |
| N7 | Wipe de ledger/`./data` tras el primer sample “válido” |
| N8 | Spacing bajado “para conseguir ciclos” el mismo día |
| N9 | IC-1 ignorado (compras bajo −5%) o IC-2 no flatten a −10% |
| N10 | Contar jornadas previas a instrumentación S10 / C2 como días de ventana |

### 4.3 Plantilla de veredicto

```
Fecha UTC: ________
config_hash: ________________________________
E_0 (cierre día 0): ________ USDT
deployed_capital: 200
effective_mode: paper
primer_tick_at: ________

Veredicto: L0_DAY0_WINDOW_GO | L0_DAY0_WINDOW_NO_GO
Razones / owner gaps: ________
Firmas: Desk Lead ________  Market Maker ________
```

---

## 5. Prohibiciones (paper-only)

- Activar live, `FORCE_REAL_MODE`, o `PAPER_TRADING=false` con ejecución real.
- Commitear o pegar API keys / secrets reales.
- Sugerir go-live como siguiente paso automático tras este freeze o el primer tick.
- Tunear spacing / notional / rango dentro de la ventana.

**Este documento no autoriza live.** Live requiere tear sheet §3 + firma dual CEO + Desk Lead (RFC-004 / ADR-007).

---

## Changelog

| Fecha | Cambio | Autor |
|-------|--------|-------|
| 2026-08-06 | E7 IC-WIRE kickoff: stub+enforce paper (`inventory_controls`) + §2.3 status | trader-market-maker |
| 2026-08-05 | A5 — freeze params L0 + DoD primer tick + go/no-go día 0 | trader-market-maker |
