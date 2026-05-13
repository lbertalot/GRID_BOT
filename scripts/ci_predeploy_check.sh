#!/bin/bash
# GridBot CI/CD Pre-Deployment Checklist
# Uso: ./scripts/ci_predeploy_check.sh

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

PASSED=0
FAILED=0
WARNINGS=0

log_pass() {
  echo -e "${GREEN}✅ $1${NC}"
  ((PASSED++))
}

log_fail() {
  echo -e "${RED}❌ $1${NC}"
  ((FAILED++))
}

log_warn() {
  echo -e "${YELLOW}⚠️  $1${NC}"
  ((WARNINGS++))
}

log_info() {
  echo -e "${BLUE}ℹ️  $1${NC}"
}

# ────────────────────────────────────────────────────────────────────────────

echo -e "${BLUE}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}GridBot CI/CD Pre-Deployment Checklist${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"

# ────────────────────────────────────────────────────────────────────────────
# 1. Git Checks
# ────────────────────────────────────────────────────────────────────────────

echo -e "${BLUE}[1/6] Git Checks${NC}"

if git rev-parse --git-dir > /dev/null 2>&1; then
  log_pass "Git repository válido"
else
  log_fail "No es un git repository"
  exit 1
fi

if [ -z "$(git status --porcelain)" ]; then
  log_pass "Working tree limpio (sin cambios no comiteados)"
else
  log_warn "Working tree sucio - hay cambios sin comitear"
  git status --short | head -5
fi

# Verifica que branch tiene commits
if git rev-parse HEAD > /dev/null 2>&1; then
  log_pass "Rama tiene commits"
else
  log_fail "Rama sin commits"
  exit 1
fi

# ────────────────────────────────────────────────────────────────────────────
# 2. Environment Variables
# ────────────────────────────────────────────────────────────────────────────

echo -e "\n${BLUE}[2/6] Environment Variables${NC}"

REQUIRED_VARS=(
  "BINANCE_API_KEY"
  "BINANCE_SECRET_KEY"
  "BINANCE_ED25519_API_KEY"
  "DATABASE_URL"
  "REDIS_URL"
  "SECRET_KEY"
)

for var in "${REQUIRED_VARS[@]}"; do
  if [ -z "${!var}" ]; then
    log_warn "ENV $var no configurado (requerido en producción)"
  else
    log_pass "ENV $var configurado"
  fi
done

# ────────────────────────────────────────────────────────────────────────────
# 3. File Structure
# ────────────────────────────────────────────────────────────────────────────

echo -e "\n${BLUE}[3/6] File Structure${NC}"

REQUIRED_FILES=(
  "Dockerfile"
  "docker-compose.yml"
  "docker-compose.local.yml"
  ".dockerignore"
  "alembic.ini"
  "requirements.txt"
  ".env"
  "secrets/binance_ed25519.pem"
  "grid_config_optimized.json"
)

for file in "${REQUIRED_FILES[@]}"; do
  if [ -f "$file" ]; then
    log_pass "Archivo encontrado: $file"
  else
    if [[ "$file" == "secrets/"* ]]; then
      log_warn "Archivo no encontrado: $file (puede estar en .gitignore)"
    else
      log_fail "Archivo requerido no encontrado: $file"
    fi
  fi
done

# ────────────────────────────────────────────────────────────────────────────
# 4. Code Quality
# ────────────────────────────────────────────────────────────────────────────

echo -e "\n${BLUE}[4/6] Code Quality${NC}"

if command -v python3 &> /dev/null; then
  # Sintaxis Python
  if python3 -m py_compile app/**/*.py 2>/dev/null; then
    log_pass "Sintaxis Python válida"
  else
    log_fail "Errores de sintaxis en código Python"
    python3 -m py_compile app/**/*.py
  fi
  
  # Lint (si está instalado)
  if command -v flake8 &> /dev/null; then
    if flake8 app/ --max-line-length=120 --ignore=E203,W503 --count --statistics | grep -q "0 errors"; then
      log_pass "Flake8 check: OK"
    else
      log_warn "Flake8 encontró issues (puede ser no-bloqueante)"
      flake8 app/ --max-line-length=120 --ignore=E203,W503 --count | tail -1
    fi
  else
    log_info "flake8 no instalado (omitiendo lint)"
  fi
else
  log_warn "Python3 no disponible (omitiendo code quality)"
fi

# ────────────────────────────────────────────────────────────────────────────
# 5. Configuration Validation
# ────────────────────────────────────────────────────────────────────────────

echo -e "\n${BLUE}[5/6] Configuration Validation${NC}"

# JSON validation
if command -v python3 &> /dev/null; then
  if python3 -c "import json; json.load(open('grid_config_optimized.json'))" 2>/dev/null; then
    log_pass "grid_config_optimized.json: JSON válido"
  else
    log_fail "grid_config_optimized.json: JSON inválido"
    exit 1
  fi
  
  if python3 -c "import json; json.load(open('alembic.ini'))" 2>/dev/null; then
    log_info "alembic.ini: Verificado"
  else
    # alembic.ini es INI, no JSON, pero al menos verificamos que existe
    if [ -f "alembic.ini" ]; then
      log_pass "alembic.ini: Encontrado"
    fi
  fi
else
  log_warn "Python3 no disponible (omitiendo validación JSON)"
fi

# ────────────────────────────────────────────────────────────────────────────
# 6. Docker Checks
# ────────────────────────────────────────────────────────────────────────────

echo -e "\n${BLUE}[6/6] Docker Checks${NC}"

if command -v docker &> /dev/null; then
  log_pass "Docker instalado"
  
  if docker --version | grep -q "Docker"; then
    DOCKER_VERSION=$(docker --version | awk '{print $3}' | sed 's/,//')
    log_info "Docker version: $DOCKER_VERSION"
  fi
  
  if command -v docker-compose &> /dev/null || docker compose version > /dev/null 2>&1; then
    log_pass "Docker Compose disponible"
  else
    log_warn "Docker Compose no encontrado"
  fi
  
  # Validar compose file
  if docker compose -f docker-compose.local.yml config > /dev/null 2>&1; then
    log_pass "docker-compose.local.yml: Sintaxis válida"
  else
    log_fail "docker-compose.local.yml: Errores de sintaxis"
    docker compose -f docker-compose.local.yml config
    exit 1
  fi
  
  if docker compose -f docker-compose.yml config > /dev/null 2>&1; then
    log_pass "docker-compose.yml: Sintaxis válida"
  else
    log_fail "docker-compose.yml: Errores de sintaxis"
    docker compose -f docker-compose.yml config
    exit 1
  fi
else
  log_warn "Docker no instalado (omitiendo Docker checks)"
fi

# ────────────────────────────────────────────────────────────────────────────
# Summary
# ────────────────────────────────────────────────────────────────────────────

echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Resumen${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "  ${GREEN}✅ Pasadas: $PASSED${NC}"
echo -e "  ${RED}❌ Fallos: $FAILED${NC}"
echo -e "  ${YELLOW}⚠️  Advertencias: $WARNINGS${NC}\n"

if [ $FAILED -gt 0 ]; then
  echo -e "${RED}CI/CD BLOQUEADO: $FAILED errores críticos encontrados${NC}"
  exit 1
fi

if [ $WARNINGS -gt 0 ]; then
  echo -e "${YELLOW}⚠️  Se encontraron $WARNINGS advertencias (revisar antes de deploy)${NC}\n"
fi

echo -e "${GREEN}✅ Pre-deployment checks PASSED!${NC}"
echo -e "   Puedes proceder con deploy\n"

exit 0
