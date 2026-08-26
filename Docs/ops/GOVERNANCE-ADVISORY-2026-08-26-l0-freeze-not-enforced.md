# Advisory de gobernanza — el freeze L0-A no gobernó la ejecución real (2026-08-05/06 → 2026-08-26)

| Campo | Valor |
|-------|-------|
| Fecha | 2026-08-26 |
| Estado | **Resuelto — N10 declarado 2026-08-26 ~12:20 UTC** (ver RCA §16). Este advisory queda como registro histórico de por qué la ventana L0-A (2026-08-05/06 → 2026-08-26) no es evidencia válida de KPI. |
| Severidad | **P0 gobernanza** (no operacional — breaker cerrado, bot paper-safe) |
| Origen | RCA `rca-pnl-dd-2026-08-20.md` §12-14 (revisión independiente `trader-market-maker` + `trader-prop`) |
| Owner | `trading-desk-lead` + `product` |
| Modo | Paper-only. **PROMOTE_LIVE: NO.** |

## Qué pasó

`app/services/trading_tasks.py:1150-1186` (código de 2025-09-16, **anterior** al freeze L0-A del 2026-08-05/06) sobreescribía en **cada tick** `min_price`/`max_price`/`grid_levels` del asset ETHUSDT a una banda de **±1% del spot actual con 3 niveles**, en vez de usar los parámetros congelados y documentados en `L0_PAPER_FREEZE_PARAMS.md` §1.1 (±5%, 10 niveles, spacing 100 bps, mid=1923.08). El hash de config (`grid_config_paper_l0.hash`, gate A1) certifica el archivo en disco, no el estado en memoria del `asset` al momento del trade — por eso el gate T2 del DoD podía pasar en verde mientras la ejecución real ya no usaba esos valores.

Adicionalmente, el `range_floor` de IC-1 (`app/core/inventory_controls.py`) se carga una sola vez por proceso desde el JSON congelado y **nunca se sincronizó** con la banda dinámica — quedó anclado a 1826.92 mientras el motor operaba contra ±1% del spot (~2450).

## Impacto en los datos de la ventana

**Los tear sheets, reportes de Capa A y KPIs generados sobre la ventana L0-A (2026-08-05/06 en adelante) no deben tratarse como evidencia válida del rendimiento de la configuración congelada documentada en `L0_PAPER_FREEZE_PARAMS.md` §1.1.** Los ciclos reales ejecutaron con spacing efectivo (~50 bps teórico, 15-30 bps observado) muy por debajo del spacing nominal (100 bps), lo que estructuralmente eleva el `cost_ratio` (24 bps RT / spacing) a 80-160% en vez del ~24% esperado por diseño — explica mecánicamente las dos rachas de pérdidas consecutivas (2026-08-20 y 2026-08-26) sin necesidad de invocar movimiento de mercado adverso.

Los datos siguen siendo reales y útiles para diagnóstico (de hecho fueron la evidencia que permitió esta RCA), pero **no representan el experimento que `L0_PAPER_FREEZE_PARAMS.md` declara estar corriendo**.

## Mitigación aplicada hoy (Paso 1 — reversible, sin cambio de spacing/sizing)

`trading_tasks.py` ahora respeta un flag explícito `ENABLE_DYNAMIC_GRID_RECENTER` (default **`false`**): con el flag apagado, el ciclo usa `min_price`/`max_price`/`grid_levels` tal como los carga `grid_config_paper_l0.json`, sin overrides en memoria. Verificado en logs (2026-08-26 11:53:45Z): con la banda congelada activa (1826.92–2019.23) y spot real ~2455, el sistema reconoce correctamente `"precios fuera de rango"` y deja de generar ciclos artificiales. **Esto detiene el patrón de pérdidas hacia adelante**, pero no valida retroactivamente los datos ya generados ni resuelve por sí solo la pregunta de fondo (¿el freeze de 1923.08 sigue vigente o corresponde declarar N10?).

## Paso 2 — ejecutado (2026-08-26, ~12:07-12:36 UTC)

Autorizado por el Desk Lead ("avancemos"). N10 declarado: nuevo freeze con `mid_price_at_freeze=2459.72`, banda ±5% (min=2336.73, max=2582.70), 100 bps / 10 niveles explícitos (no ±1%/3-niveles). Ledger anterior archivado en `paper_telemetry/archive/n10-fix-qty-2026-08-26T1220Z/`; ledger nuevo con `E_0=1000 USDT`. Durante la validación se encontró y corrigió un bug independiente en `scripts/freeze_paper_l0_config.py` (redondeo de `quantity` hacia abajo generaba un truncado por debajo del piso de USD 20 en el motor de ejecución — ver RCA §16.2). Primer fill real confirmado 12:36:37 UTC (`BUY 0.0082 ETH @ $2459.86`). Detalle completo, evidencia y go/no-go: `Docs/ops/rca-pnl-dd-2026-08-20.md` §16.

## Referencias

- `Docs/ops/rca-pnl-dd-2026-08-20.md` §12 (M1, `trader-market-maker`), §13 (M2, `trader-prop`), §14 (convergencia y escalamiento).
- `Docs/L0_PAPER_FREEZE_PARAMS.md` (config congelada original, banner de advertencia agregado).
- `app/services/trading_tasks.py` (flag `ENABLE_DYNAMIC_GRID_RECENTER`).
- `app/core/inventory_controls.py` (gap de `range_floor` desacoplado, ver RCA §13 M2.1).
