# n8n local junto a GRID_BOT (paper L0)

**Modo:** paper-only · **PROMOTE_LIVE: NO**  
**Doc upstream:** [Install using Docker Compose](https://docs.n8n.io/deploy/host-n8n/install-options/install-using-docker-compose)  
**Path:** `GRID_BOT/docker/n8n/`

## Qué incluye

| Servicio | Rol |
|----------|-----|
| `n8n` | Editor UI `http://localhost:5678` |
| `sandbox-*` | AI Assistant (código en sandbox; DinD privileged) |
| `searxng` | Búsqueda web interna del assistant |

n8n se une a la red `grid_bot_gridbot_network` → desde workflows: `http://api:8000` (health, CEO overview, ops summary).

## Requisitos

- Docker Compose v2 + stack local GRID_BOT arriba (`docker-compose.local.yml`)
- ≥ 4 GB RAM libres (sandbox DinD)

## Arranque

```bash
cd GRID_BOT/docker/n8n
cp env.example .env   # solo la primera vez; ya puede existir con secrets
# Editar .env: no dejar change-me-...

docker compose up -d
docker compose ps
```

Verificación (docs):

```bash
docker compose exec n8n wget -qO- http://sandbox-api:8080/healthz
docker compose logs sandbox-api | grep -i runner
curl -sf http://localhost:5678/healthz

# Alcance a GRID_BOT paper
docker compose exec n8n wget -qO- http://api:8000/health
```

UI: abrir `http://localhost:5678` y crear el owner en el primer login.

## License (Community / free)

UI: **Settings → Usage and plan → Enter activation key**, o en `.env`:

```bash
N8N_LICENSE_ACTIVATION_KEY=<tu-key>
docker compose up -d n8n
```

Si la instancia ya tiene licencia activada, la variable no la sobrescribe ([docs](https://docs.n8n.io/deploy/host-n8n/configure-n8n/manage-your-license)).

## AI Assistant (opcional)

Sin `N8N_INSTANCE_AI_MODEL_API_KEY` el editor funciona; el assistant queda off. Para activarlo, añadir la key al `.env` y `docker compose up -d n8n`. Ver [Set up the AI Assistant](https://docs.n8n.io/deploy/host-n8n/configure-n8n/set-up-ai-assistant.md).

## Seguridad paper

- No publicar puertos del sandbox; solo `:5678` en localhost.
- No pegar `BINANCE_*` ni secrets de trading en credenciales n8n.
- No automatizar flip live / `EMERGENCY_STOP` real / reset de breakers por PnL.
- IP allowlist Binance: checklist + 2FA humano (skill `trading-binance-ip-allowlist`).

## Parar

```bash
cd GRID_BOT/docker/n8n
docker compose down          # conserva volúmenes n8n_data + sandbox-tls
# docker compose down -v   # borra datos n8n (irreversible)
```
