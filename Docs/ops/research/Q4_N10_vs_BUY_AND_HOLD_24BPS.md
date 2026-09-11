# Q-4 — Grid N10 vs buy-and-hold ETHUSDT (offline, 24 bps RT)

Ventana paper canónica: 2026-08-15 → 2026-09-14 UTC.  
Símbolo: ETHUSDT. Coste round-trip **24 bps** (10 bps fee + 2 bps slip por lado, igual que el ledger).  
**Sin** código de ejecución. **Sin** cambiar N10 (`ff6a35fc…`). **Sin** elegir overlay 5×15 (NO-GO, 0 closes).

## Método

1. Grid: SoT `paper_equity_ledger.json` — PnL neto MtM de la ventana (E_T − E_0), ya neto de fees/slippage.
2. Buy-and-hold: comprar 1 unidad nocional en t0 (primer mid disponible de la serie/paper), vender en t1 (cierre 14-sep o último mid), restar 24 bps RT sobre el notional.
3. No optimizar spacing/niveles con estos datos (in-sample). Una sola variante congelada para Fase 2 = N10 10×20.

## Números (corte 2026-09-10, tear Fase 0)

| Estrategia | PnL neto USDT | Notas |
|------------|---------------|-------|
| Grid N10 (ledger) | **−0.9767** | E_0=1000 → E≈999.02; 19 ciclos el 26-ago; idle + SI HOLD después |
| Buy-and-hold spot | **N/A (falta mid t0/t1 independientes en este acta)** | Completar el 14-sep con mids ETHUSDT de la serie/klines públicas **sin** keys de trading |

Con PnL grid &lt; 0 y muestra A2 incompleta, B&H no se usa para seleccionar parámetros. Resultado: **no hay evidencia de edge** de N10 vs un hold pasivo en esta ventana.

**PROMOTE_LIVE: NO.** No `PROMOTE_PAPER`.
