# Calibración spacing grid ETHUSDT — 2026-08-26 (paper)

**PROMOTE_LIVE: NO.** No cambia el freeze N10 (§1) sin firma Desk Lead (N11).

## 1. Costo real de operar (ledger N10)

| Métrica | Valor |
|---------|--------|
| Fuente | `paper_telemetry/paper_equity_ledger.json` (19 ciclos cerrados) |
| Modelo | `PaperCostModel`: fee 10 bps/lado + adverse 2 bps/lado |
| BNB discount | **No** (exposición no deseada; freeze §1.2) |
| Slippage | **Supuesto declarado** (no spread bid/ask medido) |
| Costo RT medio | **≈ 24.00 bps** (0.24%) |
| Capture media (buy→sell) | **≈ −1.6 bps** (mediana +2.0) |
| Edge medio (capture − costo) | **≈ −25.6 bps** |
| Σ gross / fees / slip / net | −0.061 / +0.763 / +0.153 / **−0.977 USDT** |

**Conclusión paso 1:** el freeze de **100 bps** no es “más chico que el costo”.
El bot capturó ~0 bps porque alternaba BUY/SELL **intra-nivel** (bug Δnivel),
no porque el spacing configurado fuera 25 bps.

## 2–4. Backtest (cruce de nivel + costo 24 bps)

Script: `scripts/research/run_grid_spacing_calibration.py`  
Motor: `app/research/grid_backtest.py`  
Artefacto: `Docs/ops/research/grid-spacing-calibration-2026-08-26.json` (+ variante 1h).

Limitación: 5m ≈ 1000 velas (~3.5d). 1h ≈ 41d (más robusto).

Hallazgos (neto, no #trades):

- **25 bps** ≈ piso de costo → neto ~0 (malo).
- **75–100 bps** fijos: mejor compromiso en 5m; **100** alineado al freeze.
- **ATR×k** gana en algunos tramos 1h pero con más DD y spacing efectivo a veces ~40 bps (piso) → menos margen de seguridad vs modelo.
- En régimen trend corto, spacings anchos hacen menos trades (esperado).

## 5. Binance minNotional

| Campo | Valor |
|-------|--------|
| Filter | `NOTIONAL.minNotional` ETHUSDT Spot |
| Vigente (2026-08-26) | **5 USDT** |
| Freeze notional/nivel | **20 USDT** (headroom 4×; piso desk 15) |
| Lot step | 0.0001 ETH |

## 6. Config recomendada (sin N11)

| Ítem | Decisión |
|------|----------|
| Spacing | **Mantener 100 bps** (freeze N10) |
| Sizing | **USD 20 / nivel** |
| Código | Patch **Δnivel ≥ 1** ya en `grid_strategy.py` (no bajar spacing) |
| Si desk quiere 75 bps | Requiere **N11** + nuevo hash freeze |

## 7. Métricas paper nuevas

| Métrica Prometheus | Significado |
|--------------------|-------------|
| `paper_cycle_edge_gross_usdt` | Gross último ciclo |
| `paper_cycle_edge_net_usdt` | Net último ciclo (gross−fees−slip) |
| `paper_cycle_edge_net_cum_usdt` | Net acumulado ledger |
| `paper_consecutive_losses` | Racha actual |
| `paper_early_streak_warn` | 1 si racha ≥ `PAPER_EARLY_STREAK_WARN` (default **3**) |

Telegram temprano (debounce 1h) si racha ≥ 3; breaker duro sigue en 5.

## 8. Validación siguiente (2026-08-26) — acuerdo desk

Script: `scripts/research/validate_spacing_next_steps.py`  
Artefacto: `grid-spacing-validation-next-2026-08-26.json`

### 8.1 Historia 1h × 180d (4320 barras)

- Mejor fijo por neto: **200 bps** (net ≈ 40.8) — no implica N11 ahora.
- Mejor global backtest: **ATR×1.0** (net ≈ 94.5, capture ≈ 82 bps).
- Fijo **100 bps** con Δnivel: net ≈ **+29.3**, capture **100 bps**.

### 8.2 Ablación Δnivel≥1 vs whipsaw @ 100 bps (misma ventana)

| Modo | Trades | Capture media | Net PnL |
|------|--------|---------------|---------|
| Δnivel≥1 (patch) | 193 | **100 bps** | **+29.3** |
| Whipsaw 5 bps (proxy pre-patch) | 679 | **5 bps** | **−25.8** |

Δ captura ≈ **+95 bps**; Δ neto ≈ **+55 USDT**. Confirma: el spacing nominal de 100 ya era suficiente; faltaba captura.

### 8.3 Gate paper ATR×1.0 (escrito *antes* de adoptar)

| Campo | Valor |
|-------|--------|
| Min días calendario | **14** |
| Min ciclos cerrados | **40** |
| Métrica primaria | `paper_cycle_edge_net_cum_usdt` |
| Pass | capture media ≥ 60 bps; edge_cum > 0; sin trip SI; ATR net ≥ baseline 100 bps en la misma ventana |
| Fail / no-decidir | capture < 40; SI open; muestra &lt; 40 ciclos o &lt; 14d → **extender, no decidir** |
| Non-goals | no maximizar #trades; no bajar freeze a 75 sin N11; PROMOTE_LIVE: NO |

### 8.4 Decisión ahora

1. **No N11 de spacing.** Mantener freeze 100 bps.  
2. Prioridad: validar **Δnivel≥1 en paper** con métricas de edge neto.  
3. ATR×1.0 solo como trial paper si (y cuando) pase §8.3 — no por backtest solo.
