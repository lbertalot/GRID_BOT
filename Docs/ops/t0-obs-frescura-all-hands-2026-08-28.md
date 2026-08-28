# T0.5 — frescura de obs (All Hands, 2026-08-28)

**Modo:** paper-only · **PROMOTE_LIVE: NO**  
Plantilla de acta: T0.5 en [`ALL-HANDS-L0-GATE-PROTOCOL-2026-08-27.md`](../../../Docs/product/ALL-HANDS-L0-GATE-PROTOCOL-2026-08-27.md) (monorepo). Esta nota es la evidencia versionada en `GRID_BOT`.

## Check (leer en voz alta antes del frente 1)

| Pregunta | Evidencia | 2026-08-28 18:21 ART |
|----------|-----------|----------------------|
| Snapshot age &lt;20 min | `time()-max(portfolio_snapshot_last_unixtime{job="gridbot-api"})` | SÍ (~minutos) |
| Tick Celery 15m &gt;0 | Flower `trading_cycle_tick` succeeded | SÍ (~1/min) |
| Freno | `breaker_any_open{job="gridbot-api"}` + Redis HASH + SI REDUCE_ONLY | SÍ (ignorar Flower=0) |
| Equity | ledger / `paper_equity_usdt` job=api ≈ 999.02 | SÍ — no ROI ops |

Si T0.5 = NO → no citar Grafana como “ahora”. Puede haber HOLD real con telemetría congelada.

## No citar como estado actual

Grafana 8 h de la **mañana** del 2026-08-28 (snapshot 4+ h, Celery success=0, `GridBotTickStalled`) = incidente beat pidfile **cerrado**. Detalle: [`exec-ola0-beat-pidfile-2026-08-28.md`](exec-ola0-beat-pidfile-2026-08-28.md). Hueco 11:44–13:44 ART = recreate/obs, no wipe ledger. ETH −3,54 % 12:00–14:00 = validación HOLD, no bug.
