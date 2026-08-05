#!/usr/bin/env python3
"""
Validación pre-startup para GridBot.
Ejecutar ANTES de `docker compose up`.

Verifica:
1. Archivos críticos (Ed25519 key, config)
2. Variables de entorno requeridas
3. Credenciales Binance válidas
4. Estructura de directorios
5. Formato de configuración JSON
"""

import os
import sys
import json
from pathlib import Path
from typing import Tuple, List
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
load_dotenv()

# Colores para terminal
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"

class ValidationError(Exception):
    pass

class HealthChecker:
    def __init__(self):
        self.root = Path(__file__).parent.parent
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.checks_passed = 0
        self.checks_failed = 0

    def log_pass(self, msg: str):
        print(f"{GREEN}[PASS] {msg}{RESET}")
        self.checks_passed += 1

    def log_fail(self, msg: str, is_warning=False):
        if is_warning:
            print(f"{YELLOW}[WARN] {msg}{RESET}")
            self.warnings.append(msg)
        else:
            print(f"{RED}[FAIL] {msg}{RESET}")
            self.errors.append(msg)
            self.checks_failed += 1

    def log_info(self, msg: str):
        print(f"{BLUE}[INFO] {msg}{RESET}")

    def check_file_exists(self, path: Path, name: str, critical=True) -> bool:
        """Verifica que un archivo existe."""
        if path.exists():
            self.log_pass(f"Archivo encontrado: {name}")
            return True
        else:
            self.log_fail(f"Falta archivo crítico: {name} ({path})", is_warning=not critical)
            return False

    def check_directory_exists(self, path: Path, name: str) -> bool:
        """Verifica que un directorio existe."""
        if path.is_dir():
            self.log_pass(f"Directorio encontrado: {name}")
            return True
        else:
            self.log_fail(f"Falta directorio: {name} ({path})", is_warning=False)
            return False

    def check_env_var(self, var_name: str, required=True, pattern=None) -> str:
        """Verifica variable de entorno."""
        value = os.getenv(var_name)
        if value:
            if pattern and not pattern in str(value):
                self.log_fail(f"ENV {var_name}: valor inválido (esperaba contener '{pattern}')")
                return None
            self.log_pass(f"ENV {var_name} configurado")
            return value
        else:
            self.log_fail(f"ENV {var_name} no configurado", is_warning=not required)
            return None

    def check_json_valid(self, path: Path, name: str) -> bool:
        """Valida JSON."""
        try:
            with open(path) as f:
                json.load(f)
            self.log_pass(f"JSON válido: {name}")
            return True
        except json.JSONDecodeError as e:
            self.log_fail(f"JSON inválido en {name}: {e}")
            return False
        except FileNotFoundError:
            self.log_fail(f"Archivo no encontrado: {name}")
            return False


    def is_paper_mode(self) -> bool:
        """Modo paper efectivo: PAPER_TRADING activo y FORCE_REAL_MODE no forzado."""
        paper_trading = os.getenv("PAPER_TRADING", "true").lower() in {"1", "true", "yes", "on"}
        force_real = os.getenv("FORCE_REAL_MODE", "false").lower() in {"1", "true", "yes", "on"}
        return paper_trading and not force_real

    def check_binance_env_vars(self) -> bool:
        """Valida credenciales Binance.

        En paper el stack simula órdenes, así que credenciales ausentes o
        placeholder son advertencia y no bloquean el arranque: el checklist paper
        debe poder correrse desde un clon limpio con env.example.
        """
        paper_mode = self.is_paper_mode()
        api_key = self.check_env_var("BINANCE_API_KEY", required=not paper_mode)
        api_secret = self.check_env_var("BINANCE_SECRET_KEY", required=not paper_mode)

        if not (api_key and api_secret):
            self.log_fail("Credenciales Binance incompletas", is_warning=paper_mode)
            return paper_mode

        # Validar longitud mínima
        if len(api_key) < 30:
            self.log_fail(f"BINANCE_API_KEY demasiado corto (got {len(api_key)})", is_warning=paper_mode)
            return paper_mode
        if len(api_secret) < 60:
            self.log_fail(f"BINANCE_SECRET_KEY demasiado corto (got {len(api_secret)})", is_warning=paper_mode)
            return paper_mode

        self.log_pass("Credenciales Binance tienen formato válido (no validadas contra API)")
        return True

    def check_grid_config(self) -> bool:
        """Valida grid_config_optimized.json."""
        config_path = self.root / "grid_config_optimized.json"
        
        if not self.check_json_valid(config_path, "grid_config_optimized.json"):
            return False
        
        try:
            with open(config_path) as f:
                config = json.load(f)
            
            # Detectar símbolos (claves que no empiezan por _ y no son system_config)
            symbols = [k for k in config.keys() if not k.startswith("_") and k != "system_config"]
            
            if not symbols:
                self.log_fail("Config: no se encontraron símbolos activos")
                return False
            
            invalid_symbols = []
            for symbol in symbols:
                # Validar formato de símbolo (solo letras y números, 6-12 chars)
                if not symbol.isalnum() or len(symbol) < 6:
                    invalid_symbols.append(symbol)
            
            if invalid_symbols:
                self.log_fail(f"Símbolos con formato inválido en config: {invalid_symbols}")
                return False
            
            self.log_pass(f"Grid config válido ({len(symbols)} símbolos detectados)")
            return True
        except Exception as e:
            self.log_fail(f"Error validando grid config: {e}")
            return False

    def check_database_env(self) -> bool:
        """Valida variables de base de datos."""
        db_url = self.check_env_var("DATABASE_URL", required=True, pattern="postgresql://")
        if not db_url:
            self.log_fail("DATABASE_URL no configurado o formato inválido")
            return False
        return True

    def check_trading_mode(self) -> bool:
        """Valida consistencia del modo de trading (Paper vs Real)."""
        paper_trading = os.getenv("PAPER_TRADING", "true").lower() == "true"
        force_real = os.getenv("FORCE_REAL_MODE", "false").lower() == "true"
        trading_enabled = os.getenv("TRADING_ENABLED", "false").lower() == "true"

        # FORCE_REAL_MODE anula PAPER_TRADING en BinanceService: pedir ambos es
        # una config contradictoria que en runtime termina en real. Fail closed.
        if force_real and paper_trading:
            self.log_fail("CRÍTICO: FORCE_REAL_MODE=true junto a PAPER_TRADING=true. "
                          "FORCE_REAL_MODE anula paper; corregí la config antes de arrancar.")
            return False

        if not trading_enabled:
            self.log_info("Trading desactivado (TRADING_ENABLED=false)")
            return True

        if not paper_trading:
            if not force_real:
                self.log_fail("CRÍTICO: PAPER_TRADING=false pero FORCE_REAL_MODE no es true. "
                             "Habilita FORCE_REAL_MODE=true para confirmar trading real.")
                return False
            else:
                print(f"\n{RED}{BOLD}!!! MODO TRADING REAL ACTIVADO !!!{RESET}")
                print(f"{RED}Dinero real en riesgo. Asegurate de que las credenciales son correctas.{RESET}\n")
                self.log_pass("Modo REAL confirmado con FORCE_REAL_MODE=true")
        else:
            self.log_pass("Modo PAPER TRADING activo (simulación)")
        
        return True

    def check_redis_env(self) -> bool:
        """Valida variables Redis."""
        redis_url = self.check_env_var("REDIS_URL", required=True, pattern="redis://")
        if not redis_url:
            self.log_fail("REDIS_URL no configurado o formato inválido")
            return False
        return True

    def check_directories_writable(self) -> bool:
        """Verifica que directorios críticos existen y son escribibles."""
        dirs_to_check = [
            ("logs", self.root / "logs"),
            ("cache", self.root / "cache"),
            ("data", self.root / "data"),
            ("monitoring_data", self.root / "monitoring_data"),
            ("reports", self.root / "reports"),
            ("secrets", self.root / "secrets"),
        ]
        
        all_valid = True
        for name, path in dirs_to_check:
            if not path.exists():
                path.mkdir(parents=True, exist_ok=True)
                self.log_pass(f"Directorio creado: {name}")
            else:
                self.log_pass(f"Directorio existe: {name}")
            
            # Validar permisos de escritura (salvo secrets que es read-only)
            if name != "secrets":
                test_file = path / ".write_test"
                try:
                    test_file.touch()
                    test_file.unlink()
                except PermissionError:
                    self.log_fail(f"Directorio no escribible: {name}")
                    all_valid = False
        
        return all_valid

    def check_docker_compose_file(self) -> bool:
        """Verifica que docker-compose.yml existe."""
        compose_file = self.root / "docker-compose.local.yml"
        return self.check_file_exists(compose_file, "docker-compose.local.yml")

    def check_alembic_config(self) -> bool:
        """Verifica Alembic setup."""
        alembic_ini = self.root / "alembic.ini"
        alembic_dir = self.root / "alembic"
        
        if not self.check_file_exists(alembic_ini, "alembic.ini"):
            return False
        if not self.check_directory_exists(alembic_dir, "alembic/"):
            return False
        
        return True

    def run_all_checks(self) -> bool:
        """Ejecuta todas las validaciones."""
        print(f"\n{BOLD}{BLUE}--- GridBot Pre-Startup Validation ---{RESET}\n")
        print(f"Root directory: {self.root}\n")

        # Fase 1: Archivos críticos
        print(f"{BOLD}[1/5] Archivos críticos:{RESET}")
        self.check_docker_compose_file()
        self.check_alembic_config()

        # Fase 2: Variables de entorno
        print(f"\n{BOLD}[2/5] Variables de entorno:{RESET}")
        self.check_binance_env_vars()
        self.check_database_env()
        self.check_redis_env()

        # Fase 3: Configuración JSON
        print(f"\n{BOLD}[3/5] Configuración y Modo:{RESET}")
        self.check_grid_config()
        self.check_trading_mode()

        # Fase 4: Directorios
        print(f"\n{BOLD}[4/5] Estructura de directorios:{RESET}")
        self.check_directories_writable()

        # Fase 5: .env file
        print(f"\n{BOLD}[5/5] Archivo .env:{RESET}")
        env_file = self.root / ".env"
        self.check_file_exists(env_file, ".env", critical=False)

        # Resumen
        print(f"\n{BOLD}{BLUE}========================================={RESET}")
        print(f"{BOLD}Resumen:{RESET}")
        print(f"  {GREEN}[PASS] Pasadas: {self.checks_passed}{RESET}")
        print(f"  {RED}[FAIL] Fallos: {self.checks_failed}{RESET}")
        print(f"  {YELLOW}[WARN] Advertencias: {len(self.warnings)}{RESET}")
        print(f"{BOLD}{BLUE}========================================={RESET}\n")

        if self.checks_failed > 0:
            print(f"{RED}{BOLD}[FAIL] STARTUP BLOCKED: Errores criticos encontrados{RESET}\n")
            for error in self.errors:
                print(f"  {RED}*{RESET} {error}")
            return False
        
        if self.warnings:
            print(f"{YELLOW}[WARN] Advertencias detectadas (revisar):{RESET}\n")
            for warning in self.warnings:
                print(f"  {YELLOW}*{RESET} {warning}")
        
        print(f"{GREEN}{BOLD}[PASS] Pre-startup checks PASSED! Puedes ejecutar:{RESET}")
        print(f"  docker compose -f docker-compose.local.yml up --build\n")
        return True

if __name__ == "__main__":
    checker = HealthChecker()
    success = checker.run_all_checks()
    sys.exit(0 if success else 1)
