# GridBot Makefile — Comandos para desarrollo, testing y deployment
# Uso: make [target]

.PHONY: help validate validate-strict up down logs check-health cleanup \
        test test-unit test-integration db-reset db-seed format lint \
        build push docs

PROJECT := grid_bot
COMPOSE_FILE := docker-compose.local.yml
PYTHON := python3
DOCKER := docker
DOCKER_COMPOSE := docker compose

help: ## Muestra esta ayuda
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ────────────────────────────────────────────────────────────────────────────
# 🔍 VALIDACIÓN
# ────────────────────────────────────────────────────────────────────────────

validate: ## Valida pre-startup (archivos, env, credenciales)
	@echo "🔍 Ejecutando validación pre-startup..."
	@$(PYTHON) scripts/validate_startup.py
	@exit $$?

validate-strict: validate ## Validación + quita volúmenes antes de startup
	@echo "🗑️  Limpiando volúmenes anteriores..."
	@$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) -p $(PROJECT) down -v

# ────────────────────────────────────────────────────────────────────────────
# 🚀 DOCKER COMPOSE
# ────────────────────────────────────────────────────────────────────────────

up: ## Levanta stack completo (usa validate primero)
	@$(MAKE) validate
	@echo "🚀 Levantando GridBot..."
	@$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) -p $(PROJECT) up -d --build
	@echo "⏳ Esperando a que servicios estén listos..."
	@sleep 10
	@$(MAKE) check-health

down: ## Detiene todos los servicios
	@echo "⬇️  Parando GridBot..."
	@$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) -p $(PROJECT) down

restart: down up ## Reinicia servicios

logs: ## Muestra logs en vivo (todos los servicios)
	@$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) -p $(PROJECT) logs -f

logs-api: ## Logs del API
	@$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) -p $(PROJECT) logs -f api

logs-worker: ## Logs del worker Celery
	@$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) -p $(PROJECT) logs -f worker

logs-db: ## Logs de PostgreSQL
	@$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) -p $(PROJECT) logs -f db

logs-redis: ## Logs de Redis
	@$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) -p $(PROJECT) logs -f redis

# ────────────────────────────────────────────────────────────────────────────
# 🏥 HEALTH CHECKS
# ────────────────────────────────────────────────────────────────────────────

check-health: ## Post-startup health checks (API, DB, Redis, Celery, Binance)
	@echo "🏥 Ejecutando health checks post-startup..."
	@$(PYTHON) scripts/health_check_startup.py
	@exit $$?

check-health-continuous: ## Health checks en loop (cada 30s)
	@echo "🔄 Health checks continuos (Ctrl+C para detener)..."
	@while true; do \
		clear; \
		$(PYTHON) scripts/health_check_startup.py; \
		echo "\n⏳ Próximo check en 30s..."; \
		sleep 30; \
	done

check-containers: ## Lista estado de contenedores
	@$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) -p $(PROJECT) ps

check-volumes: ## Lista volúmenes
	@$(DOCKER) volume ls | grep $(PROJECT)

# ────────────────────────────────────────────────────────────────────────────
# 🗑️  LIMPIEZA
# ────────────────────────────────────────────────────────────────────────────

cleanup: ## Limpia containers y volúmenes (DESTRUCTIVO)
	@echo "⚠️  Limpiando ALL containers, volúmenes e imágenes de $(PROJECT)..."
	@$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) -p $(PROJECT) down -v --rmi all
	@echo "✅ Limpieza completada"

cleanup-soft: ## Limpia solo volúmenes (mantiene images)
	@echo "🗑️  Limpiando volúmenes..."
	@$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) -p $(PROJECT) down -v
	@echo "✅ Volúmenes eliminados"

cleanup-logs: ## Limpia archivos de log locales
	@echo "📝 Limpiando logs locales..."
	@rm -rf logs/*
	@mkdir -p logs
	@echo "✅ Logs limpios"

cleanup-cache: ## Limpia caché local
	@echo "💾 Limpiando caché..."
	@rm -rf cache/*
	@mkdir -p cache
	@echo "✅ Caché limpió"

# ────────────────────────────────────────────────────────────────────────────
# 🗄️  BASE DE DATOS
# ────────────────────────────────────────────────────────────────────────────

db-reset: ## Reinicia DB (DESTRUCTIVO - borra datos)
	@echo "⚠️  Reseteando base de datos..."
	@$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) -p $(PROJECT) exec -T db psql -U griduser -d gridbot -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
	@echo "✅ DB reseteada"

db-migrate: ## Ejecuta migraciones Alembic
	@echo "📊 Ejecutando migraciones..."
	@$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) -p $(PROJECT) exec api alembic upgrade head
	@echo "✅ Migraciones completadas"

db-shell: ## Abre psql interactivo
	@$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) -p $(PROJECT) exec db psql -U griduser -d gridbot

redis-cli: ## Abre redis-cli interactivo
	@$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) -p $(PROJECT) exec redis redis-cli

# ────────────────────────────────────────────────────────────────────────────
# ✅ TESTING
# ────────────────────────────────────────────────────────────────────────────

test: test-unit test-integration ## Ejecuta todos los tests

test-unit: ## Tests unitarios
	@echo "🧪 Ejecutando tests unitarios..."
	@$(PYTHON) -m pytest tests/unit -v --cov=app --cov-report=term-missing
	@exit $$?

test-integration: ## Tests de integración (requiere servicios corriendo)
	@echo "🧪 Ejecutando tests de integración..."
	@$(PYTHON) -m pytest tests/integration -v -s
	@exit $$?

test-fast: ## Tests rápidos (sin integración)
	@$(PYTHON) -m pytest tests/ -v -k "not integration" --durations=10
	@exit $$?

# ────────────────────────────────────────────────────────────────────────────
# 🎨 CÓDIGO
# ────────────────────────────────────────────────────────────────────────────

format: ## Formatea código (black, isort)
	@echo "🎨 Formateando código..."
	@$(PYTHON) -m black app/ tests/
	@$(PYTHON) -m isort app/ tests/
	@echo "✅ Código formateado"

lint: ## Lint (flake8, pylint, mypy)
	@echo "🔍 Linting..."
	@$(PYTHON) -m flake8 app/ tests/ --max-line-length=120 --ignore=E203,W503
	@$(PYTHON) -m mypy app/ --ignore-missing-imports
	@echo "✅ Lint OK"

check-code: format lint ## Formatea + lint

# ────────────────────────────────────────────────────────────────────────────
# 📚 DOCUMENTACIÓN
# ────────────────────────────────────────────────────────────────────────────

docs: ## Genera documentación (mkdocs)
	@echo "📚 Generando documentación..."
	@$(PYTHON) -m mkdocs serve

docs-build: ## Build documentación estática
	@$(PYTHON) -m mkdocs build

# ────────────────────────────────────────────────────────────────────────────
# 🏗️  BUILD & PUSH
# ────────────────────────────────────────────────────────────────────────────

build: ## Build images locales
	@echo "🏗️  Building images..."
	@$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) -p $(PROJECT) build

build-no-cache: ## Build sin caché (limpio)
	@echo "🏗️  Building (no cache)..."
	@$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) -p $(PROJECT) build --no-cache

# ────────────────────────────────────────────────────────────────────────────
# 📋 WORKFLOW COMPLETO
# ────────────────────────────────────────────────────────────────────────────

full-reset: ## Reset completo: down, cleanup, validate, up, health-check
	@$(MAKE) down
	@$(MAKE) cleanup-soft
	@$(MAKE) cleanup-logs
	@$(MAKE) cleanup-cache
	@$(MAKE) validate
	@$(MAKE) up
	@$(MAKE) check-health

quick-start: validate up check-health ## Quick start: valida + sube + chequea

dev: ## Modo desarrollo: up con logs
	@$(MAKE) up
	@$(MAKE) logs

# ────────────────────────────────────────────────────────────────────────────

.DEFAULT_GOAL := help
