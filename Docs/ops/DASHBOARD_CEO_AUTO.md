# Tablero CEO — Cómo va la prueba (paper)

**URL:** http://localhost:3000/d/gridbot-ceo-auto/gridbot-como-va-la-prueba-paper  
**UID:** `gridbot-ceo-auto`  
**Modo:** paper-only · **PROMOTE_LIVE: NO**  
**SoT equity:** `paper_equity_usdt` (ledger), **no** `profit_total_usdt` / dash Rentabilidad.

## Para qué es

Que el CEO, en **5 segundos**, vea: ¿sigue el ensayo?, ¿cuánta “nafta” ficticia queda?, ¿el semáforo pide paciencia o intervenir?

Analogía: tablero de un auto, no cockpit de avión.

## Para qué no es

- No prueba que el bot **gane plata** (MtM ≠ edge). El veredicto de ventaja es el **tear Capa A** de la noche.
- No reemplaza Health SRE (ops) ni el digest Telegram (desk).
- No es gate live.

## Semáforo (igual que el digest)

| Color | Condición | Acción CEO |
|-------|-----------|------------|
| Verde | paper + API up + cambio vs inicio **> −1,5%** + sin emergencia/IP | Nada |
| Naranja | paper y (cambio **≤ −1,5% y > −3%** **o** freno HOLD) | Esperar. No live. No resetear frenos. |
| Rojo capital | cambio **≤ −3%** (grave) o **≤ −5%** (pausa) | Desk interviene. No live. |
| Rojo sistema | no-paper **o** servidor caído **o** emergency stop **o** gauge `binance_ip_rejected=1` (IP rechazada **ahora**, no el corte ya reparado) | servidor / lista de IPs |

El freno `system_integrity` por pérdidas seguidas es **naranja (HOLD)**, no rojo de “resetear ahora”.

## Smoke (Grafana ya up)

1. Abrir la URL (refresh provisioning ~10 s; si no aparece: restart `gridbot_grafana` o esperar).
2. **Modo** = PAPER · **Live: NO**.
3. **Balance** ≈ equity del digest Telegram / `paper_equity_usdt`.
4. Con Δ ≈ −1,8% el **semáforo es NARANJA**, no rojo sistema.
5. **Antigüedad de la foto** no muestra “56 años” (solo job API, unixtime > 1e9).

## P1 (no bloquea)

| Hueco | Owner |
|-------|--------|
| Gauge `paper_equity_dd_pct` (evitar PromQL largo) | `trading-backend-tdd` |
| `desk_digest_global_status` 0/1/2 | backend + desk |
| Pie BTC/ETH/cash | Defer — no hay SoT L0 |
| Ciclos “con ganancia” | Defer — realized_net no está en Prom |

## Relacionados

- Health SRE: `/d/gridbot-health-sre` — ¿está vivo?
- Paper L0: `/d/gridbot-paper-l0` — ops
- Runbook: `OBS_RUNBOOK_PAPER_L0.md`
- Telegram CEO (mismo semáforo, menos jerga): `TELEGRAM_CEO_PLAIN.md`
