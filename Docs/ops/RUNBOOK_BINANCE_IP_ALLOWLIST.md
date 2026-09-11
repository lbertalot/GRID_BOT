# Runbook humano — Binance IP allowlist (−2015)

Paper-only · **PROMOTE_LIVE: NO**. Cursor **no** ejecuta 2FA ni cambia la whitelist.

Skill de operador (browser, 2FA humano): `trading-binance-ip-allowlist` en el monorepo `.cursor/skills/`.  
Checklist R-6 (key sin withdraw): también [`breakers-process-scope.md`](breakers-process-scope.md) §Checklist humano R-6.

## Cuándo

Telegram: `Binance no acepta esta conexión` / incidente `binance_auth_ip_blocked`. Gauge `binance_ip_rejected=1` o Redis `gridbot:binance_auth_ip_blocked=1`. API/worker pueden seguir `up`.

## Pasos (humano)

1. Validar IP pública del **host/worker** (`curl -4 ifconfig.me` o `GET /ip` si existe). Puede no coincidir con el egreso si hay proxy — anotar ambas.
2. En Binance → Gestión de API, comparar con la allowlist. **No pegar keys ni secrets** en chat/git/Telegram.
3. Agregar la IP en MASTER `gridbot-ws-v3` y READ `readonly_gridbot`. Restricción de IPs confiables **ON**. **Withdraw / retiro: OFF** (R-6).
4. Guardar con **2FA humano** (app + email). Nadie del squad (ni Cursor) completa este paso.
5. Confirmar recovery: una llamada autenticada python-binance OK (gauge `binance_ip_rejected=0` **y** Telegram “Binance autenticó de nuevo”). No asumir “se retoma solo” en el aviso de apertura.
6. Anotar en acta desk: `IP allowlist + withdraw OFF verificados YYYY-MM-DD` · **PROMOTE_LIVE: NO**.

## Ambigüedades resueltas en este runbook

| Antes | Ahora |
|-------|--------|
| ¿R-6 (withdraw) vs IP son el mismo paso? | Mismo panel Binance; withdraw OFF es obligatorio en el paso 3 junto con allowlist. |
| ¿Quién hace 2FA? | Solo humano Desk/operador; Cursor no. |
| ¿Proxy vs IP del host? | Paso 1: anotar ambas si difieren. |

## Prohibido

Resetear `system_integrity` de PnL/NO-GO, `DEL` Redis HASH, `FORCE_REAL_MODE`, live, wipe ledger, cambiar permisos de la key a withdraw ON, pegar la key en logs.
