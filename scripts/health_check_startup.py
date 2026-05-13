#!/usr/bin/env python3
"""
Health check post-startup para GridBot.
Ejecutar DESPUÉS de `docker compose up`.

Verifica:
1. Todos los contenedores están en estado 'running'
2. Health checks pasan (si están configurados)
3. Endpoints clave responden (API, Prometheus, Grafana)
4. Binance API es accesible
5. Base de datos está lista
6. Redis está listo
7. Workers de Celery están activos
"""

import subprocess
import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional
import requests

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"

class PostStartupChecker:
    def __init__(self, project_name="grid_bot"):
        self.project = project_name
        self.checks_passed = 0
        self.checks_failed = 0
        self.warnings: List[str] = []

    def log_pass(self, msg: str):
        print(f"{GREEN}✅ {msg}{RESET}")
        self.checks_passed += 1

    def log_fail(self, msg: str, is_warning=False):
        if is_warning:
            print(f"{YELLOW}⚠️  {msg}{RESET}")
            self.warnings.append(msg)
        else:
            print(f"{RED}❌ {msg}{RESET}")
            self.checks_failed += 1

    def log_info(self, msg: str):
        print(f"{BLUE}ℹ️  {msg}{RESET}")

    def run_command(self, cmd: List[str]) -> tuple[bool, str]:
        """Ejecuta comando shell."""
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            return result.returncode == 0, result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            return False, "Command timeout"
        except Exception as e:
            return False, str(e)

    def get_containers(self) -> Dict[str, Dict]:
        """Obtiene estado de todos los contenedores del proyecto."""
        success, output = self.run_command([
            "docker", "compose", "-p", self.project, "ps", "--format", "json"
        ])
        
        if not success:
            self.log_fail("No se pudieron obtener contenedores (¿está Docker corriendo?)")
            return {}
        
        try:
            containers = json.loads(output)
            return {c["Name"]: c for c in containers}
        except json.JSONDecodeError:
            return {}

    def check_container_running(self, name: str) -> bool:
        """Verifica que un contenedor está running."""
        containers = self.get_containers()
        
        for cname, info in containers.items():
            if name in cname:
                state = info.get("State", "unknown").lower()
                if state == "running":
                    self.log_pass(f"Contenedor {name}: RUNNING")
                    return True
                else:
                    self.log_fail(f"Contenedor {name}: {state.upper()}")
                    return False
        
        self.log_fail(f"Contenedor {name} no encontrado")
        return False

    def check_http_endpoint(self, url: str, name: str, expected_status=200, retries=5) -> bool:
        """Verifica que un endpoint HTTP responde."""
        for attempt in range(retries):
            try:
                response = requests.get(url, timeout=5)
                if response.status_code == expected_status:
                    self.log_pass(f"Endpoint {name}: OK ({response.status_code})")
                    return True
                else:
                    self.log_fail(f"Endpoint {name}: status {response.status_code} (esperaba {expected_status})")
                    return False
            except requests.ConnectionError:
                if attempt < retries - 1:
                    time.sleep(2)
                    continue
                self.log_fail(f"Endpoint {name}: no responde después de {retries} intentos")
                return False
            except Exception as e:
                self.log_fail(f"Endpoint {name}: error {e}")
                return False
        
        return False

    def check_docker_logs_for_errors(self, service: str, keywords: List[str]) -> Optional[str]:
        """Busca keywords de error en logs de contenedor."""
        success, output = self.run_command([
            "docker", "compose", "-p", self.project, "logs", service, "--tail", "50"
        ])
        
        if not success:
            return None
        
        for keyword in keywords:
            if keyword.lower() in output.lower():
                return f"Encontrado en logs: {keyword}"
        
        return None

    def check_binance_connectivity(self) -> bool:
        """Verifica que el worker puede conectar a Binance (por logs)."""
        api_logs = self.check_docker_logs_for_errors("worker", [
            "APIError(code=-2015)",
            "Falta clave privada Ed25519",
            "Invalid API-key"
        ])
        
        if api_logs:
            self.log_fail(f"Binance error: {api_logs}", is_warning=True)
            return False
        
        success_logs = self.check_docker_logs_for_errors("worker", [
            "trading_cycle_tick succeeded",
            "Cliente Binance Singleton inicializado"
        ])
        
        if success_logs:
            self.log_pass("Binance API: conectado y autenticado")
            return True
        
        self.log_fail("Binance: estado desconocido (revisar logs)", is_warning=True)
        return False

    def check_database_connectivity(self) -> bool:
        """Verifica que la DB está lista."""
        success, output = self.run_command([
            "docker", "compose", "-p", self.project, "exec", "-T", "db",
            "pg_isready", "-U", "griduser", "-d", "gridbot"
        ])
        
        if success:
            self.log_pass("PostgreSQL: listo y accesible")
            return True
        else:
            self.log_fail("PostgreSQL: no accesible")
            return False

    def check_redis_connectivity(self) -> bool:
        """Verifica que Redis está listo."""
        success, output = self.run_command([
            "docker", "compose", "-p", self.project, "exec", "-T", "redis",
            "redis-cli", "ping"
        ])
        
        if "PONG" in output:
            self.log_pass("Redis: listo (PONG)")
            return True
        else:
            self.log_fail("Redis: no responde")
            return False

    def check_celery_workers_active(self) -> bool:
        """Verifica que hay workers activos."""
        worker_logs = self.check_docker_logs_for_errors("worker", [
            "celery@",
            "ready",
            "Connected to redis"
        ])
        
        if worker_logs:
            self.log_pass("Celery worker: activo")
            return True
        
        self.log_fail("Celery worker: no listo", is_warning=True)
        return False

    def check_migrations_completed(self) -> bool:
        """Verifica que migraciones se ejecutaron exitosamente."""
        success, output = self.run_command([
            "docker", "compose", "-p", self.project, "logs", "migrate", "--tail", "20"
        ])
        
        if "Migraciones aplicadas" in output or "already at head" in output:
            self.log_pass("Alembic migrations: completadas")
            return True
        else:
            self.log_fail("Alembic migrations: no completadas")
            return False

    def run_all_checks(self) -> bool:
        """Ejecuta todas las validaciones post-startup."""
        print(f"\n{BOLD}{BLUE}🏥 GridBot Post-Startup Health Check{RESET}\n")
        print(f"Proyecto: {self.project}\n")

        # Fase 1: Contenedores
        print(f"{BOLD}[1/5] Contenedores:{RESET}")
        containers_ok = all([
            self.check_container_running("db"),
            self.check_container_running("redis"),
            self.check_container_running("api"),
            self.check_container_running("worker"),
            self.check_container_running("beat"),
            self.check_container_running("flower"),
            self.check_container_running("prometheus"),
            self.check_container_running("grafana"),
        ])

        # Fase 2: Servicios críticos
        print(f"\n{BOLD}[2/5] Servicios críticos:{RESET}")
        self.check_database_connectivity()
        self.check_redis_connectivity()
        self.check_migrations_completed()

        # Fase 3: Endpoints HTTP
        print(f"\n{BOLD}[3/5] Endpoints HTTP:{RESET}")
        self.check_http_endpoint("http://localhost:8000/health", "API /health")
        self.check_http_endpoint("http://localhost:9090/-/healthy", "Prometheus health")
        self.check_http_endpoint("http://localhost:3000/api/health", "Grafana health")
        self.check_http_endpoint("http://localhost:5555/", "Flower", expected_status=401)  # Auth requerido

        # Fase 4: Aplicación
        print(f"\n{BOLD}[4/5] Aplicación:{RESET}")
        self.check_celery_workers_active()
        self.check_binance_connectivity()

        # Fase 5: Logs sin errores críticos
        print(f"\n{BOLD}[5/5] Análisis de logs:{RESET}")
        api_errors = self.check_docker_logs_for_errors("api", [
            "CRITICAL",
            "Fatal",
            "Traceback"
        ])
        
        if not api_errors:
            self.log_pass("API logs: sin errores críticos")
        else:
            self.log_fail(f"API logs: {api_errors}", is_warning=True)

        # Resumen
        print(f"\n{BOLD}{BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}")
        print(f"{BOLD}Resumen:{RESET}")
        print(f"  {GREEN}✅ Pasadas: {self.checks_passed}{RESET}")
        print(f"  {RED}❌ Fallos: {self.checks_failed}{RESET}")
        print(f"  {YELLOW}⚠️  Advertencias: {len(self.warnings)}{RESET}")
        print(f"{BOLD}{BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}\n")

        if self.checks_failed > 0:
            print(f"{RED}{BOLD}❌ HEALTH CHECK FAILED:{RESET}\n")
            print(f"Verifica logs con:")
            print(f"  docker compose -p {self.project} logs -f [service]\n")
            return False
        
        if self.warnings:
            print(f"{YELLOW}⚠️  Revisa advertencias:{RESET}\n")
            for w in self.warnings:
                print(f"  • {w}\n")
        
        print(f"{GREEN}{BOLD}✅ GridBot está READY!{RESET}\n")
        print(f"Dashboards:")
        print(f"  API:        http://localhost:8000")
        print(f"  Grafana:    http://localhost:3000 (admin/gridbot123)")
        print(f"  Prometheus: http://localhost:9090")
        print(f"  Flower:     http://localhost:5555 (admin/admin)\n")
        
        return True

if __name__ == "__main__":
    checker = PostStartupChecker()
    success = checker.run_all_checks()
    sys.exit(0 if success else 1)
