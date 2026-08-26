# Slice E-SELL-CLIP — residual SELL paper (deadlock L0)

**Owner:** `trading-backend-tdd` · EM: este doc  
**Prioridad:** P0 paper L0 · **PROMOTE_LIVE: NO**  
**Repo:** `GRID_BOT/`  
**No wipe** telemetry · no cambio de `config_hash`

## Problema
Tras N10 hay 1 BUY de **0,0053 ETH** (~10 USDT, pre-parche sizer).  
`last_action=BUY` → el grid pide **SELL**. El sizer L0 pide **~0,0106 ETH** (nivel 20).  
Fund manager / check `notional < min_notional_threshold` rechazan. No hay BUY (ya compró). **0 fills en el día.**

Grafana `Operaciones=0` es además `gridbot_orders_total` (no SoT). El SoT es el ledger.

## Contrato

| Caso | Comportamiento |
|------|----------------|
| Paper SELL | `qty = min(sizer, ledger.position(symbol))` redondeado a `step_size` (floor) |
| `position == 0` | no enviar SELL |
| Residual &lt; nivel 20 (p.ej. 10 USDT) | **sí vender** — no aplicar piso 15/20 al cierre de inventario |
| BUY | sin cambio: sizer 20 + cap `deployed_capital=200` |
| Live / no-paper | no cambia |

Punto de corte: **antes** de `fund_manager.validate_trade_requirements` y **no** `continue` por `notional < min_notional_threshold` en SELL paper residual.

Helper preferido: `app/core/paper_cycle_liquidity.py` (`clip_paper_sell_quantity`).

## TDD
`tests/test_paper_sell_clip_residual.py` (red→green). Decimal. Mocks, sin Binance real.

## Validación EM (2026-08-14 23:45 UTC)

| Capa | Veredicto | Evidencia |
|------|-----------|-----------|
| TDD slice | **PROMOTE_PAPER** | pytest `test_paper_sell_clip_residual.py` + `test_paper_cycle_liquidity.py` **11 passed** |
| Runtime L0 | **PROMOTE_PAPER** (integridad) | Worker recreate 23:42Z → ciclo 23:44:56Z clip `0.0106→0.0053` → SELL FILLED. Ledger `updated_at` 23:44:58Z. `cyc-7318c6ebf570` **closed**. Fills: BUY + SELL. |

Revenue / edge: **NO-GO** (1 round-trip, PnL neto ≈ −0,058 USDT). **PROMOTE_LIVE: NO.** No wipe.

| Caso | Resultado |
|------|-----------|
| Clip 0.0106 → 0.0053 | PASS (TDD + runtime) |
| position 0 → skip | PASS (TDD) |
| no-paper sin clip | PASS (TDD) |
| residual ~10 USDT no aborta por piso 20 | PASS (TDD + runtime; también bypass Binance min 10: notional 9,97) |

P2: log `step=0` (limits `step_size` no llegó al clip; qty ya era 0,0053). Grafana `Operaciones` sigue sin SoT ledger (P1 obs).

## Fuera de alcance
Spacing, sizing freeze, Grafana `gridbot_orders_total` (P1 obs), wipe, live.
