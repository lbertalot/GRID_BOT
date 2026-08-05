# Checklist: fallos silenciosos de observabilidad

Patrones donde el stack “parece sano” pero la señal operativa es inútil.
Modo por defecto: **paper / dry-run**. No implica gate live.

## Patrones “healthy pero inútil”

| Patrón | Señal engañosa | Cómo detectarlo |
|--------|----------------|-----------------|
| Healthz superficial | Contenedor `healthy`, `/healthz` 200 | Probar el contrato de datos (p. ej. cAdvisor `/api/v1.3/docker` no vacío) |
| `up` sin datos | `up{job="cadvisor"}==1` | Contar series reales: `count(container_cpu_usage_seconds_total{id!="/"}) >= 1` |
| Logs E/W sin alerta | Logs de machine-id / factory en stderr | Alertas Prometheus + revisión de rules; logs solos no abren incidente |
| CEO cards `unavailable` | HTTP 200 en overview/dashboard | Inspeccionar `.status` / campos de cada card (`ok`/`stale`/`unavailable`) |

### cAdvisor (caso post-auditoría)

1. `healthz` solo prueba el proceso HTTP.
2. Factory Docker rota (p. ej. falta `containerd.sock` en Desktop) → `/api/v1.3/docker` = `{}` y Prometheus puede scrapear solo el root `id="/"`.
3. Alertas en `docker/prometheus/rules/cadvisor_silent_failure_rules.yml`:
   - `CadvisorTargetDown` — scrape muerto.
   - `CadvisorNoContainerMetrics` — scrape vivo sin series por contenedor.

## Smoke post-compose (mínimo)

Puertos por defecto: Prometheus `9090`, cAdvisor `8081` (override con `PROMETHEUS_URL` / `CADVISOR_URL`).

```bash
# Script (recomendado)
make smoke-observability

# O copy-paste
curl -sf http://localhost:8081/api/v1.3/docker | jq 'length'   # > 0
curl -sf 'http://localhost:9090/api/v1/query?query=up%7Bjob%3D%22cadvisor%22%7D' \
  | jq -e '.data.result[0].value[1] == "1"'
curl -sf 'http://localhost:9090/api/v1/query?query=count(container_cpu_usage_seconds_total%7Bid!%3D%22%2F%22%7D)' \
  | jq -e '(.data.result[0].value[1] | tonumber) >= 1'
```

También en [`Docs/BOOTSTRAP_PAPER.md`](../BOOTSTRAP_PAPER.md) §5.

## Checklist operador (post `make up`)

- [ ] `make smoke-paper` → `effective_mode=paper`
- [ ] `make smoke-observability` → PASS (docker API + target up + series `id!="/"`)
- [ ] Prometheus → Status → Targets: job `cadvisor` **UP**
- [ ] Alertmanager / rules: no firing sostenido de `CadvisorTargetDown` / `CadvisorNoContainerMetrics`
- [ ] CEO overview: cards capital/ops no en error 500; `unavailable` documentado si aplica (PnL MTD)
- [ ] Sin secrets reales en logs ni compose

## Gaps residuales (no cubiertos por estas alertas)

- Healthcheck compose que solo mira `healthz` (si aún no exige discovery Docker).
- Logs E/W de machine-id sin regla de log-based alerting.
- `up` de otros exporters (redis/postgres) sin validar que las métricas de negocio existan.
- CEO `unavailable` por wiring de datos (ADR PnL) — no es fallo de scrape.

Paper-first. Live solo con autorización humana explícita.
