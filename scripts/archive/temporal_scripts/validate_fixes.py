#!/usr/bin/env python3
"""
Script de Validación de Correcciones de Auditoría
GridBot v2.5

Valida que todas las correcciones implementadas están correctas.
"""

import sys
import ast
import re
from pathlib import Path
from typing import List


class ValidationReport:
    def __init__(self):
        self.passed = []
        self.failed = []
        self.warnings = []

    def add_pass(self, test: str, message: str):
        self.passed.append((test, message))

    def add_fail(self, test: str, message: str):
        self.failed.append((test, message))

    def add_warning(self, test: str, message: str):
        self.warnings.append((test, message))

    def print_report(self):
        print("\n" + "=" * 80)
        print("📋 REPORTE DE VALIDACIÓN DE CORRECCIONES")
        print("=" * 80)

        print(f"\n✅ PASADAS: {len(self.passed)}")
        for test, msg in self.passed:
            print(f"   ✓ {test}: {msg}")

        if self.warnings:
            print(f"\n⚠️  ADVERTENCIAS: {len(self.warnings)}")
            for test, msg in self.warnings:
                print(f"   ⚠ {test}: {msg}")

        if self.failed:
            print(f"\n❌ FALLIDAS: {len(self.failed)}")
            for test, msg in self.failed:
                print(f"   ✗ {test}: {msg}")

        print("\n" + "=" * 80)
        total = len(self.passed) + len(self.failed)
        success_rate = (len(self.passed) / total * 100) if total > 0 else 0
        print(f"TASA DE ÉXITO: {success_rate:.1f}% ({len(self.passed)}/{total})")
        print("=" * 80)

        return len(self.failed) == 0


def validate_syntax(files: List[Path], report: ValidationReport):
    """Validar sintaxis de archivos Python"""
    for file in files:
        try:
            with open(file, "r", encoding="utf-8") as f:
                ast.parse(f.read())
            report.add_pass("Sintaxis", f"{file.name} ✓")
        except SyntaxError as e:
            report.add_fail("Sintaxis", f"{file.name}: {e}")


def validate_async_functions(files: List[Path], report: ValidationReport):
    """Validar que funciones con asyncio.to_thread son async"""
    for file in files:
        with open(file, "r", encoding="utf-8") as f:
            content = f.read()

        # Buscar funciones con asyncio.to_thread
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_source = ast.get_source_segment(content, node)
                if func_source and "asyncio.to_thread" in func_source:
                    if isinstance(node, ast.AsyncFunctionDef):
                        report.add_pass("Async", f"{file.name}::{node.name} es async ✓")
                    else:
                        report.add_fail(
                            "Async",
                            f"{file.name}::{node.name} usa to_thread pero NO es async",
                        )


def validate_no_blocking_io(files: List[Path], report: ValidationReport):
    """Validar que no quedan llamadas bloqueantes sin asyncio.to_thread"""
    blocking_patterns = [
        r"client\.get_account\(\)",
        r"client\.get_symbol_ticker\(",
        r"client\.create_order\(",
        r"requests\.post\(",
        r"requests\.get\(",
        r"(?<!asyncio\.to_thread\().*open\(",
    ]

    for file in files:
        with open(file, "r", encoding="utf-8") as f:
            lines = f.readlines()

        found_blocking = False
        for i, line in enumerate(lines, 1):
            # Ignorar comentarios y líneas con asyncio.to_thread
            if line.strip().startswith("#") or "asyncio.to_thread" in line:
                continue

            for pattern in blocking_patterns:
                if re.search(pattern, line):
                    report.add_fail(
                        "Blocking I/O", f"{file.name}:{i} - {line.strip()[:60]}"
                    )
                    found_blocking = True

        if not found_blocking:
            report.add_pass("Blocking I/O", f"{file.name} sin llamadas bloqueantes ✓")


def validate_imports(files: List[Path], report: ValidationReport):
    """Validar que asyncio está importado donde se usa"""
    for file in files:
        with open(file, "r", encoding="utf-8") as f:
            content = f.read()

        uses_asyncio_to_thread = "asyncio.to_thread" in content
        has_asyncio_import = "import asyncio" in content

        if uses_asyncio_to_thread:
            if has_asyncio_import:
                report.add_pass("Imports", f"{file.name} tiene import asyncio ✓")
            else:
                report.add_fail(
                    "Imports", f"{file.name} usa to_thread sin importar asyncio"
                )


def validate_tests(test_files: List[Path], report: ValidationReport):
    """Validar estructura de tests"""
    for file in test_files:
        with open(file, "r", encoding="utf-8") as f:
            content = f.read()

        # Contar tests
        test_count = content.count("def test_")
        if test_count > 0:
            report.add_pass("Tests", f"{file.name} tiene {test_count} tests ✓")
        else:
            report.add_warning("Tests", f"{file.name} no tiene funciones de test")

        # Verificar imports pytest
        if "import pytest" in content:
            report.add_pass("Tests", f"{file.name} importa pytest ✓")
        else:
            report.add_warning("Tests", f"{file.name} no importa pytest")


def main():
    root = Path("/Users/leandrobertalot/Documents/grid_bot")

    # Archivos modificados en las correcciones
    modified_files = [
        root / "app/main_simple.py",
        root / "app/core/balance_validator.py",
        root / "app/api/test_routes.py",
        root / "app/api/prometheus.py",
        root / "app/strategies/dca_strategy.py",
        root / "app/strategies/scalping_strategy.py",
    ]

    # Archivos de test creados
    test_files = [
        root / "tests/test_trade_executor.py",
        root / "tests/test_balance_service.py",
        root / "tests/test_binance_user_stream.py",
    ]

    report = ValidationReport()

    print("🔍 Iniciando validación de correcciones...")
    print("=" * 80)

    print("\n1️⃣ Validando sintaxis...")
    validate_syntax(modified_files + test_files, report)

    print("2️⃣ Validando funciones async...")
    validate_async_functions(modified_files, report)

    print("3️⃣ Validando eliminación de blocking I/O...")
    validate_no_blocking_io(modified_files, report)

    print("4️⃣ Validando imports...")
    validate_imports(modified_files, report)

    print("5️⃣ Validando tests...")
    validate_tests(test_files, report)

    # Imprimir reporte final
    success = report.print_report()

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
