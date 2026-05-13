# 🔍 GridBot Validation & Health Check Procedure

## 📋 Tabla de Contenidos
1. [Pre-Startup Validation](#pre-startup-validation)
2. [Post-Startup Health Checks](#post-startup-health-checks)
3. [Troubleshooting](#troubleshooting)
4. [Automated Monitoring](#automated-monitoring)

---

## Pre-Startup Validation

### ¿Cuándo ejecutar?
- **Antes de cada `docker compose up`**
- Después de cambios en `.env` o credenciales
- Después de agregar nuevos símbolos a `grid_config_optimized.json`
- En pipelines CI/CD antes de deployar

### ¿Cómo ejecutar?

**Opción 1: Script directo**
```bash
python3 scripts/validate_startup.py
```

**Opción 2: Make (recomendado)**
```bash
make validate
```

### ✅ Qué valida

| Check | Descripción | Crítico |
|-------|-------------|---------|
| **Archivos críticos** | Verifica que existen `secrets/binance_ed25519.pem`, `docker-compose.local.yml`, `alembic.ini` | ✅ Sí |
| **Variables Binance** | `BINANCE_API_KEY`, `BINANCE_SECRET_KEY`, `BINANCE_ED25519_API_KEY` configuradas | ✅ Sí |
| **Clave Ed25519** | Valida que `secrets/binance_ed25519.pem` existe y tiene formato válido | ✅ Sí |
| **Configuración JSON** | `grid_config_optimized.json` válido y símbolos en formato correcto | ✅ Sí |
| **Base de datos** | `DATABASE_URL` configurada con formato `postgresql://...` | ✅ Sí |
| **Redis** | `REDIS_URL` configurada con formato `redis://...` | ✅ Sí |
| **Directorios** | Existen y son escribibles: `logs/`, `cache/`, `data/`, `reports/`, `monitoring_data/`, `secrets/` | ❌ No |
| **Archivo .env** | Debe existir en root | ❌ No |

### 🔴 Si falla (Critical)

**Error: "CRÍTICO: Falta clave Ed25519"**
```bash
# Solución: Crear archivo con tu clave privada Ed25519
cat > secrets/binance_ed25519.pem << 'EOF'
-----BEGIN PRIVATE KEY-----
[TU_CLAVE_PRIVADA_AQUI]
-----END PRIVATE KEY-----
EOF
chmod 600 secrets/binance_ed25519.pem
```

**Error: "ENV BINANCE_API_KEY no configurado"**
```bash
# Edita .env
nano .env
# Agrega:
# BINANCE_API_KEY=tu_api_key_aqui
# BINANCE_SECRET_KEY=tu_secret_key_aqui
# BINANCE_ED25519_API_KEY=tu_ed25519_public_key_aqui
```

**Error: "Símbolos inválidos en config"**
```bash
# Revisa grid_config_optimized.json
# Los símbolos deben ser:
# - Formato: XXXYYY (ej: ETHUSDT, BNBUSDT)
# - O: XXX/YYY (ej: ETH/USDT, BNB/USDT)
# INCORRECTO: LDBNBUSDT, LDUSDTUSDT
# CORRECTO: ETHUSDT, BNBUSDT
```

### 🟡 Si hay advertencias (Non-critical)

Puedes continuar pero revisar después:
- Missing `.env` → crear uno vacío, usa valores por defecto
- Directorio no existente → se crea automáticamente

---

## Post-Startup Health Checks

### ¿Cuándo ejecutar?
- **Inmediatamente después de `docker compose up`**
- Antes de comenzar a tradear
- En monitoring continuo (cada 30-60s)
- Después de deployar actualizaciones

### ¿Cómo ejecutar?

**Opción 1: Una sola vez**
```bash
python3 scripts/health_check_startup.py
```

**Opción 2: Make (recomendado)**
```bash
make check-health
```

**Opción 3: Loop continuo (monitoreo)**
```bash
make check-health-continuous
# O manual:
while true; do 
  python3 scripts/health_check_startup.py; 
  sleep 30; 
done
```

### ✅ Qué valida

| Check | Descripción | Acción |
|-------|-------------|--------|
| **Contenedores running** | Verifica que todos están en estado "running" | Restart si es necesario |
| **PostgreSQL** | Verifica conectividad y `pg_isready` | Revisar logs de `db` |
| **Redis** | Verifica con `redis-cli ping` | Revisar logs de `redis` |
| **API /health** | GET `http://localhost:8000/health` debe retornar 200 | Revisar logs de `api` |
| **Prometheus** | GET `http://localhost:9090/-/healthy` debe retornar 200 | Revisar logs de `prometheus` |
| **Grafana** | GET `http://localhost:3000/api/health` debe retornar 200 | Revisar logs de `grafana` |
| **Flower** | GET `http://localhost:5555/` debe retornar 401 (auth required) | Revisar logs de `flower` |
| **Migraciones** | Verifica que `alembic upgrade head` ejecutó en `migrate` | Revisar logs de `migrate` |
| **Celery workers** | Verifica que workers están activos en logs | Revisar logs de `worker` |
| **Binance API** | Busca errores de credenciales en logs de `worker` | Ver sección Troubleshooting |
| **Sin errores críticos** | Escanea logs buscando CRITICAL, Fatal, Traceback | Revisar logs específicos |

### 🟢 Si PASA (todo OK)

```
✅ GridBot está READY!

Dashboards:
  API:        http://localhost:8000
  Grafana:    http://localhost:3000 (admin/gridbot123)
  Prometheus: http://localhost:9090
  Flower:     http://localhost:5555 (admin/admin)
```

**Puedes empezar a tradear (o en paper trading)**

### 🔴 Si FALLA

Revisa logs del servicio específico:

**API no responde:**
```bash
make logs-api
# Busca: ERROR, Traceback, CRITICAL
```

**PostgreSQL:**
```bash
make logs-db
# Busca: FATAL, "cannot accept connections"
```

**Redis:**
```bash
make logs-redis
# Busca: "error", "bind"
```

**Celery Worker:**
```bash
make logs-worker
# Busca: ERROR, "APIError(code=-2015)", "Falta clave privada"
```

---

## Troubleshooting

### Problema: "Falta clave privada Ed25519" en Worker

**Causa:** `secrets/binance_ed25519.pem` no existe o path inválido

**Solución:**
```bash
# 1. Verifica que existe el archivo
ls -la secrets/binance_ed25519.pem

# 2. Si no existe, créalo con tu clave
cat > secrets/binance_ed25519.pem << 'EOF'
-----BEGIN PRIVATE KEY-----
[TU_CLAVE_ED25519_AQUI]
-----END PRIVATE KEY-----
EOF

# 3. Reinicia
make down
make up
make check-health
```

### Problema: "APIError(code=-2015)" - IP no whitelisted

**Causa:** Tu IP no está en whitelist de Binance

**Síntoma en logs:**
```
⚠️ Binance -2015 (IP no autorizada) para ETHUSDT
🌐 IP pública actual: 143.105.137.83
```

**Solución:**
1. Abre https://www.binance.com/es/account/security/ip-whitelist
2. Haz click en "Add IP address"
3. Agrega: `143.105.137.83` (o tu IP actual)
4. Guarda cambios
5. Espera 5 minutos
6. Reinicia worker: `docker compose restart worker`
7. Verifica: `make logs-worker` - busca "trading_cycle_tick succeeded"

### Problema: "Invalid symbol"

**Causa:** Símbolos mal formados en `grid_config_optimized.json`

**Síntoma:**
```
APIError(code=-1121): Invalid symbol. LDBNBUSDT
```

**Solución:**
```bash
# 1. Revisa el archivo
cat grid_config_optimized.json | grep symbols

# 2. Los símbolos VÁLIDOS son:
# - ETHUSDT (base + quote sin separador)
# - ETH/USDT (base / quote)

# 3. Símbolos INVÁLIDOS:
# - LDBNBUSDT (prefijo incorrecto)
# - LDUSDTUSDT (formato corrupto)

# 4. Corrige y reinicia
make down
make cleanup-cache
make up
make check-health
```

### Problema: "database is locked" (PostgreSQL)

**Causa:** Múltiples conexiones simultáneas

**Solución:**
```bash
# 1. Resetea DB
make db-reset

# 2. Reinicia
make restart
make check-health
```

### Problema: "Worker no ejecuta tasks"

**Síntoma:** `flower` muestra 0 tasks, logs silenciosos

**Causa:** Redis no está accessible o worker no conectó

**Solución:**
```bash
# 1. Verifica Redis
make redis-cli
> ping  # debe retornar PONG
> exit

# 2. Reinicia worker
docker compose restart worker

# 3. Verifica
make logs-worker | grep "ready\|Connected"
```

### Problema: Contenedor API crashea en startup

**Síntoma:** `docker compose ps` muestra API como "exited"

**Solución:**
```bash
# 1. Ver logs del crash
make logs-api

# 2. Common issues:
# - ModuleNotFoundError: revisar requirements.txt, rebuild
# - psycopg2 error: DB no está ready, esperar o restart
# - ORM error: migrations no ejecutaron, check migrate logs

# 3. Rebuild y restart
make build-no-cache
make down
make up
make check-health
```

---

## Automated Monitoring

### Opción 1: GitHub Actions CI/CD

Crear `.github/workflows/validate.yml`:
```yaml
name: Pre-Deployment Validation

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Pre-startup validation
        run: python3 scripts/validate_startup.py
      - name: Code quality
        run: |
          make lint
          make format --check
```

### Opción 2: Local Git Hook

Crear `.git/hooks/pre-push` (automático antes de push):
```bash
#!/bin/bash
set -e

echo "🔍 Running pre-push validation..."
python3 scripts/validate_startup.py

if [ $? -ne 0 ]; then
  echo "❌ Validation failed. Push blocked."
  exit 1
fi

echo "✅ Validation passed. Proceeding with push."
```

Hacer ejecutable:
```bash
chmod +x .git/hooks/pre-push
```

### Opción 3: Scheduled Health Checks (Grafana/Prometheus)

Dentro de Grafana, crea alertas basadas en métricas:
- API response time > 5s
- Worker task failure rate > 5%
- DB connections > 90
- Redis memory > 200MB
- Binance circuit breaker abierto

---

## 📊 Health Check Output Guide

### ✅ Todo OK
```
✅ GridBot está READY!
```

### ⚠️ Advertencias (revisar después)
```
⚠️ Binance: estado desconocido (revisar logs)
```

### 🔴 Errores críticos (bloquea startup)
```
❌ HEALTH CHECK FAILED:
  • Contenedor api: exited
  • Endpoint API /health: status 500
```

---

## ⏰ Checklist de Lanzamiento

Antes de tradear en VIVO (no paper trading):

- [ ] ✅ Pre-startup validation: `make validate`
- [ ] ✅ Stack arriba: `make up`
- [ ] ✅ Health checks: `make check-health`
- [ ] ✅ Binance IP whitelisted (revisar logs de worker)
- [ ] ✅ Paper trading: probado exitosamente
- [ ] ✅ Credenciales validadas (check logs)
- [ ] ✅ Símbolos configurados correctamente
- [ ] ✅ Alertas Telegram funcionando
- [ ] ✅ Grafana mostrando métricas
- [ ] ✅ Flower muestra tasks ejecutándose

---

## 🆘 Contacto / Soporte

- **Logs locales:** `./logs/gridbot.log`
- **Container logs:** `make logs-[service]`
- **Database:** `make db-shell`
- **Redis:** `make redis-cli`
- **Documentación:** https://gridbot.readthedocs.io/

---

**Última actualización:** 2026-05-13  
**Versión:** 2.5.0
