# Telegram CEO — español llano (paper L0)

**Default:** `TELEGRAM_CEO_PLAIN=true` (un solo chat).  
**Desk técnico:** `TELEGRAM_DESK_VERBOSE=true` (lista ACCIONES + copy viejo si además `TELEGRAM_CEO_PLAIN=false`).  
**PROMOTE_LIVE: NO.**

Alineado al tablero [Cómo va la prueba](DASHBOARD_CEO_AUTO.md).

## Qué llega al CEO

| Evento | Mensaje | Anti-spam |
|--------|---------|-----------|
| Digest | Semáforo + balance ensayo + “qué hago” | Solo si cambia el estado, o EOD, o rojo sistema |
| HOLD pérdidas / SI | Causa técnica (`breaker_type`, estado, motivo). NO-GO no se presenta como pérdida nueva. Racha histórica separada. | Al abrir o al cambiar estado; recordatorio **cada 6 h** (env 6–12 h) |
| Freno levantado (PnL) | Aviso inmediato “freno levantado” · `Modo: PAPER · Dinero real: NO` | Solo si hay **transición** abierto→cerrado (memoria de estado); un snapshot cerrado aislado no avisa |
| HOLD red/clave | Seguí el aviso de IP | Máx. 1 cada 6 h (mismo canal SI hold) |
| REMEDIADO | Freno de *conexión* levantado (no es PnL) | En cada reset auth/net |
| IP −2015 (`binance_auth_ip_blocked`) | IP observada + “no se retoma solo” | 1 al abrir; reaviso 6–12 h; 1 al recuperarse **solo** tras auth python-binance OK |
| ACCIONES MM/QUANT | **No** se mandan | Quedan en log / day-plan |
| Alertmanager WARNING Flower (`PaperSnapshotStale` @ flower) | **No** se mandan | Falso positivo; unixtime=0 |
| Snapshot API realmente >20m | Chequeo de estado retrasado (llano) | Máx. 1 cada 12 h |

## Qué no se manda

`AT_RISK`, `GET /api/breakers`, `samples=`, owners, spacing/sizing, “acción requerida” al CEO, `PROMOTE_LIVE` (se dice **Dinero real: NO**), cada BUY/SELL.

## Semáforo

- **Verde:** prueba andando. No hagas nada.
- **Naranja:** aviso (−1,5%) y/o freno activo. El freno **no** implica una pérdida nueva. Esperá. No live. No resetear. Recordatorio **6 h** + aviso al levantarse.
- **Rojo capital:** −3% / −5%. El equipo interviene. No live.
- **Rojo sistema:** no-paper, servidor, IP. El ensayo está a ciegas.

El % vs inicio es **valor estimado**, no ganancia. El HOLD de `system_integrity` se explica con motivo técnico (p. ej. NO-GO SI 5×15). La racha se lee del ledger (SoT); si no hay lectura, el copy dice “consultar ledger” y **no inventa un número**. Una causa no clasificada se presenta como integridad en revisión, nunca como pérdidas consecutivas. No resetear a mano; revisar el acta/tear sheet.

## Código

`app/core/telegram_ceo_copy.py` · `ceo_digest_text()` · `format_alertmanager_ceo` · `desk_status_tasks` debounce Redis `gridbot:tg:ceo:*`.
