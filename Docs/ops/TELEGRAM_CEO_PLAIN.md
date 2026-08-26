# Telegram CEO — español llano (paper L0)

**Default:** `TELEGRAM_CEO_PLAIN=true` (un solo chat).  
**Desk técnico:** `TELEGRAM_DESK_VERBOSE=true` (lista ACCIONES + copy viejo si además `TELEGRAM_CEO_PLAIN=false`).  
**PROMOTE_LIVE: NO.**

Alineado al tablero [Cómo va la prueba](DASHBOARD_CEO_AUTO.md).

## Qué llega al CEO

| Evento | Mensaje | Anti-spam |
|--------|---------|-----------|
| Digest | Semáforo + balance ensayo + “qué hago” | Solo si cambia el estado, o EOD, o rojo sistema |
| HOLD pérdidas | Freno de protección — no lo resetees | Máx. 1 cada 12 h si no cambia |
| HOLD red/clave | Seguí el aviso de IP | Máx. 1 cada 12 h |
| REMEDIADO | Freno de *conexión* levantado (no es PnL) | En cada reset auth/net |
| IP −2015 | Agregá `{ip}` en Binance | Cooldown 30 min (ya existía) |
| ACCIONES MM/QUANT | **No** se mandan | Quedan en log / day-plan |
| Alertmanager WARNING Flower (`PaperSnapshotStale` @ flower) | **No** se mandan | Falso positivo; unixtime=0 |
| Snapshot API realmente >20m | Chequeo de estado retrasado (llano) | Máx. 1 cada 12 h |

## Qué no se manda

`AT_RISK`, `GET /api/breakers`, `samples=`, owners, spacing/sizing, “acción requerida” al CEO, `PROMOTE_LIVE` (se dice **Dinero real: NO**), cada BUY/SELL.

## Semáforo

- **Verde:** prueba andando. No hagas nada.
- **Naranja:** aviso (−1,5%) y/o freno HOLD. Esperá. No live.
- **Rojo capital:** −3% / −5%. El equipo interviene. No live.
- **Rojo sistema:** no-paper, servidor, IP. El ensayo está a ciegas.

El % vs inicio es **valor estimado**, no ganancia. El HOLD de pérdidas **no** se saca solo.

## Código

`app/core/telegram_ceo_copy.py` · `ceo_digest_text()` · `format_alertmanager_ceo` · `desk_status_tasks` debounce Redis `gridbot:tg:ceo:*`.
