# DoD Docker — stack local (`docker-compose.local.yml`)

**Objetivo:** arranque verificable, secretos fuera del repo y **trading real desactivado por defecto** en compose.

**Referencias:** `AGENTS.md` (comandos), `Docs/EGRESS_API_KEYS_RUNBOOK.md` (promoción a claves reales), `Docs/PASSIVE_INCOME_EVOLUTION_PHASED_PLAN.md`.

---

## 1. Prerrequisitos

- [ ] Docker Engine + Compose v2 instalados.
- [ ] Archivo **`.env` en la raíz** (no versionar credenciales; partir de `env.example` si existe).
- [ ] Ninguna API key real en `docker-compose*.yml` ni en Markdown del repo.

---

## 2. Defaults seguros en `x-app-env` (compose local)

| Variable | Valor por defecto en repo | Nota |
|----------|---------------------------|------|
| `PAPER_TRADING` | `true` | Simulación en app; no envía órdenes reales a Binance mientras paper esté activo en código. |
| `TRADING_ENABLED` | `false` | Ciclo de trading deshabilitado hasta activación explícita (API/config/operador). |
| `EMERGENCY_STOP` | `false` | Para parada de emergencia encender `true` antes de reiniciar servicios. |
| `FORCE_REAL_MODE` | vacío / ausente | No forzar modo real sobre paper en entornos de desarrollo. |

Para pruebas con ciclo encendido **en paper**, el operador puede poner `TRADING_ENABLED: "true"` solo en su `.env` o override documentado — jamás commitear claves reales.

---

## 3. Secuencia de arranque

```bash
docker compose -f docker-compose.local.yml up --build -d
```

- [ ] El servicio **`migrate`** termina con éxito (`condition: service_completed_successfully` antes de `api` / `worker`).
- [ ] **`db`** y **`redis`** en estado healthy.
- [ ] Contenedor **`api`** responde:

```bash
curl -sf http://localhost:8000/health
```

- [ ] (Opcional) `curl -sf http://localhost:8000/metrics | head` expone texto Prometheus.

---

## 4. Apagado y datos

```bash
docker compose -f docker-compose.local.yml down
# Con borrado de volúmenes (destructivo):
# docker compose -f docker-compose.local.yml down -v
```

---

## 5. Verificación automática (contrato en CI / local)

```bash
python3.11 -m pytest tests/test_docker_local_dod_contract_p1.py -q
```

---

## 6. Promoción fuera de “solo local”

Antes de `FORCE_REAL_MODE`, claves sin restricción o `TRADING_ENABLED` persistente en producción:

1. Completar `Docs/EGRESS_API_KEYS_RUNBOOK.md` (whitelist / NAT).
2. Revisar `EMERGENCY_STOP`, breakers y `Docs/EGRESS_API_KEYS_RUNBOOK.md` §5 (monitoreo egress).
