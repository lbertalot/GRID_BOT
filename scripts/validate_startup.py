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
        print(f"{GREEN}✅ {msg}{RESET}")
        self.checks_passed += 1

    def log_fail(self, msg: str, is_warning=False):
        if is_warning:
            print(f"{YELLOW}⚠️  {msg}{RESET}")
            self.warnings.append(msg)
        else:
            print(f"{RED}❌ {msg}{RESET}")
            self.errors.append(msg)
            self.checks_failed += 1

    def log_info(self, msg: str):
        print(f"{BLUE}ℹ️  {msg}{RESET}")

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

    def check_ed25519_key(self) -> bool:
        """Valida existencia de Ed25519 key."""
        key_path = self.root / "secrets" / "binance_ed25519.pem"
        if not key_path.exists():
            self.log_fail(f"CRÍTICO: Falta clave Ed25519 en {key_path}")
            return False
        
        try:
            with open(key_path) as f:
                content = f.read()
                if "BEGIN PRIVATE KEY" not in content:
                    self.log_fail("Clave Ed25519 inválida (formato incorrecto)")
                    return False
            self.log_pass("Clave Ed25519 válida")
            return True
        except Exception as e:
            self.log_fail(f"Error leyendo clave Ed25519: {e}")
            return False

    def check_binance_env_vars(self) -> bool:
        """Valida credenciales Binance."""
        api_key = self.check_env_var("BINANCE_API_KEY", required=True)
        api_secret = self.check_env_var("BINANCE_SECRET_KEY", required=True)
        ed25519_key = self.check_env_var("BINANCE_ED25519_API_KEY", required=True)
        
        if not (api_key and api_secret and ed25519_key):
            self.log_fail("CRÍTICO: Credenciales Binance incompletas")
            return False
        
        # Validar longitud mínima
        if len(api_key) < 30:
            self.log_fail(f"BINANCE_API_KEY demasiado corto (got {len(api_key)})")
            return False
        if len(api_secret) < 60:
            self.log_fail(f"BINANCE_SECRET_KEY demasiado corto (got {len(api_secret)})")
            return False
        
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
            
            # Validaciones básicas
            if "symbols" not in config:
                self.log_fail("Config: falta 'symbols'")
                return False
            
            symbols = config.get("symbols", [])
            invalid_symbols = []
            
            for symbol in symbols:
                # Valida que tenga formato XXX/YYY o XXXYYY
                if "/" in symbol:
                    parts = symbol.split("/")
                    if len(parts) != 2 or not all(p.isalpha() for p in parts):
                        invalid_symbols.append(symbol)
                else:
                    # XXXYYY debe terminar con una moneda conocida
                    if not any(symbol.endswith(coin) for coin in ["USDT", "BUSD", "BTC", "ETH"]):
                        invalid_symbols.append(symbol)
            
            if invalid_symbols:
                self.log_fail(f"Símbolos inválidos en config: {invalid_symbols}")
                return False
            
            self.log_pass(f"Grid config válido ({len(symbols)} símbolos)")
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
        print(f"\n{BOLD}{BLUE}🔍 GridBot Pre-Startup Validation{RESET}\n")
        print(f"Root directory: {self.root}\n")

        # Fase 1: Archivos críticos
        print(f"{BOLD}[1/5] Archivos críticos:{RESET}")
        self.check_ed25519_key()
        self.check_docker_compose_file()
        self.check_alembic_config()

        # Fase 2: Variables de entorno
        print(f"\n{BOLD}[2/5] Variables de entorno:{RESET}")
        self.check_binance_env_vars()
        self.check_database_env()
        self.check_redis_env()

        # Fase 3: Configuración JSON
        print(f"\n{BOLD}[3/5] Configuración:{RESET}")
        self.check_grid_config()

        # Fase 4: Directorios
        print(f"\n{BOLD}[4/5] Estructura de directorios:{RESET}")
        self.check_directories_writable()

        # Fase 5: .env file
        print(f"\n{BOLD}[5/5] Archivo .env:{RESET}")
        env_file = self.root / ".env"
        self.check_file_exists(env_file, ".env", critical=False)

        # Resumen
        print(f"\n{BOLD}{BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}")
        print(f"{BOLD}Resumen:{RESET}")
        print(f"  {GREEN}✅ Pasadas: {self.checks_passed}{RESET}")
        print(f"  {RED}❌ Fallos: {self.checks_failed}{RESET}")
        print(f"  {YELLOW}⚠️  Advertencias: {len(self.warnings)}{RESET}")
        print(f"{BOLD}{BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}\n")

        if self.checks_failed > 0:
            print(f"{RED}{BOLD}❌ STARTUP BLOCKED: Errores críticos encontrados{RESET}\n")
            for error in self.errors:
                print(f"  {RED}•{RESET} {error}")
            return False
        
        if self.warnings:
            print(f"{YELLOW}⚠️  Advertencias detectadas (revisar):{RESET}\n")
            for warning in self.warnings:
                print(f"  {YELLOW}•{RESET} {warning}")
        
        print(f"{GREEN}{BOLD}✅ Pre-startup checks PASSED! Puedes ejecutar:{RESET}")
        print(f"  docker compose -f docker-compose.local.yml up --build\n")
        return True

if __name__ == "__main__":
    checker = HealthChecker()
    success = checker.run_all_checks()
    sys.exit(0 if success else 1)
