#!/usr/bin/env python3
"""
Audit Engine for GridBot v2.5
Performs comprehensive codebase analysis across 7 categories
"""

import os
import json
import ast
import re
from pathlib import Path
from typing import Dict, List, Set
from datetime import datetime


class GridBotAuditor:
    def __init__(self, root_path: str):
        self.root = Path(root_path)
        self.findings = {
            "unused_code": [],
            "duplicate_code": [],
            "code_quality": [],
            "performance": [],
            "documentation": [],
            "configuration": [],
            "testing": [],
        }
        self.stats = {
            "total_files_analyzed": 0,
            "total_lines_of_code": 0,
            "services_count": 0,
            "scripts_count": 0,
            "tests_count": 0,
        }

    def get_all_python_files(self, directory: str) -> List[Path]:
        """Get all Python files in a directory recursively"""
        path = self.root / directory
        if not path.exists():
            return []
        return list(path.rglob("*.py"))

    def get_file_imports(self, filepath: Path) -> Set[str]:
        """Extract all imports from a Python file"""
        imports = set()
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            imports.add(alias.name)
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            imports.add(node.module)
        except Exception:
            pass
        return imports

    def find_unused_services(self) -> List[Dict]:
        """Find services that are never imported"""
        services = self.get_all_python_files("app/services")
        services = [s for s in services if s.name != "__init__.py"]

        # Get all files that could import services
        all_files = (
            self.get_all_python_files("app")
            + self.get_all_python_files("tests")
            + self.get_all_python_files("scripts")
        )

        unused = []
        for service in services:
            service_name = service.stem
            module_path = f"app.services.{service_name}"

            # Search for imports of this service
            found = False
            for file in all_files:
                if file == service:
                    continue
                imports = self.get_file_imports(file)
                if module_path in imports or any(
                    service_name in imp for imp in imports
                ):
                    found = True
                    break

            if not found:
                # Double check with grep
                result = (
                    os.popen(
                        f'grep -r "from app.services.{service_name}" {self.root} --include="*.py" 2>/dev/null | wc -l'
                    )
                    .read()
                    .strip()
                )
                if int(result) == 0:
                    unused.append(
                        {
                            "file": str(service.relative_to(self.root)),
                            "type": "unused_service",
                            "severity": "MEDIUM",
                            "reason": "Service never imported in codebase",
                        }
                    )

        return unused

    def find_duplicate_services(self) -> List[Dict]:
        """Find services with v1/v2 or similar duplicates"""
        services = self.get_all_python_files("app/services")
        service_names = [s.stem for s in services if s.name != "__init__.py"]

        duplicates = []
        checked = set()

        for name in service_names:
            if name in checked:
                continue

            # Look for versions
            if name.endswith("_v2"):
                base = name[:-3]
                if base in service_names:
                    duplicates.append(
                        {
                            "files": [
                                f"app/services/{base}.py",
                                f"app/services/{name}.py",
                            ],
                            "type": "versioned_duplicate",
                            "severity": "HIGH",
                            "reason": f"Both {base} and {name} exist. Deprecate v1 if v2 is active.",
                        }
                    )
                    checked.add(base)
                    checked.add(name)

            # Look for backups
            if "_backup" in name or "_old" in name:
                duplicates.append(
                    {
                        "file": f"app/services/{name}.py",
                        "type": "backup_file",
                        "severity": "LOW",
                        "reason": "Backup file should be removed or moved to archive",
                    }
                )
                checked.add(name)

        return duplicates

    def find_unused_scripts(self) -> List[Dict]:
        """Find scripts not referenced in docs or Makefile"""
        scripts = self.get_all_python_files("scripts")

        # Check Makefile references
        makefile_content = ""
        makefile_path = self.root / "Makefile"
        if makefile_path.exists():
            with open(makefile_path, "r") as f:
                makefile_content = f.read()

        # Check documentation references
        doc_files = (
            list((self.root / "docs").rglob("*.md"))
            if (self.root / "docs").exists()
            else []
        )
        doc_files += [self.root / "README.md", self.root / "AGENTS.md"]
        doc_content = ""
        for doc in doc_files:
            if doc.exists():
                with open(doc, "r", encoding="utf-8") as f:
                    doc_content += f.read() + "\n"

        unused = []
        for script in scripts:
            script_name = script.name
            if script_name not in makefile_content and script_name not in doc_content:
                # Check if it's a recent utility or test script
                if any(
                    keyword in script_name
                    for keyword in ["test_", "validate_", "audit_"]
                ):
                    severity = "LOW"
                else:
                    severity = "MEDIUM"

                unused.append(
                    {
                        "file": str(script.relative_to(self.root)),
                        "type": "unreferenced_script",
                        "severity": severity,
                        "reason": "Script not referenced in Makefile or documentation",
                    }
                )

        return unused

    def find_blocking_io_in_async(self) -> List[Dict]:
        """Find blocking I/O calls in async functions"""
        issues = []
        python_files = self.get_all_python_files("app")

        blocking_patterns = [
            r"requests\.(get|post|put|delete|patch)",
            r"time\.sleep\(",
            r"client\.create_order\(",  # Binance sync client
            r"client\.get_account\(",
            r"open\(",  # File I/O without async
        ]

        for file in python_files:
            try:
                with open(file, "r", encoding="utf-8") as f:
                    content = f.read()

                # Parse AST to find async functions
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.AsyncFunctionDef):
                        func_name = node.name
                        func_start = node.lineno

                        # Get function body as string
                        lines = content.split("\n")
                        func_body = "\n".join(lines[func_start - 1 : node.end_lineno])

                        # Check for blocking patterns
                        for pattern in blocking_patterns:
                            if re.search(pattern, func_body):
                                # Check if it's wrapped in asyncio.to_thread
                                if (
                                    "asyncio.to_thread" not in func_body
                                    and "await"
                                    not in func_body.split(pattern)[0].split("\n")[-1]
                                ):
                                    issues.append(
                                        {
                                            "file": str(file.relative_to(self.root)),
                                            "function": func_name,
                                            "line": func_start,
                                            "type": "blocking_io_in_async",
                                            "severity": "HIGH",
                                            "pattern": pattern,
                                            "reason": "Blocking I/O call in async function without asyncio.to_thread",
                                        }
                                    )
                                    break
            except Exception:
                pass

        return issues

    def find_missing_type_hints(self) -> List[Dict]:
        """Find functions without type hints in critical modules"""
        issues = []
        critical_paths = ["app/services", "app/api", "app/core"]

        for path in critical_paths:
            python_files = self.get_all_python_files(path)

            for file in python_files:
                try:
                    with open(file, "r", encoding="utf-8") as f:
                        content = f.read()

                    tree = ast.parse(content)
                    for node in ast.walk(tree):
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            # Check for return type hint
                            has_return_hint = node.returns is not None

                            # Check for argument type hints
                            has_arg_hints = all(
                                arg.annotation is not None
                                for arg in node.args.args
                                if arg.arg not in ["self", "cls"]
                            )

                            if not has_return_hint or not has_arg_hints:
                                issues.append(
                                    {
                                        "file": str(file.relative_to(self.root)),
                                        "function": node.name,
                                        "line": node.lineno,
                                        "type": "missing_type_hints",
                                        "severity": "MEDIUM",
                                        "missing": "return"
                                        if not has_return_hint
                                        else "arguments",
                                        "reason": "Function missing type hints",
                                    }
                                )
                except Exception:
                    pass

        return issues

    def find_unused_env_vars(self) -> List[Dict]:
        """Find env vars defined but not used"""
        issues = []

        # Get env vars from env.example
        env_example = self.root / "env.example"
        if not env_example.exists():
            env_example = self.root / ".env"

        if not env_example.exists():
            return issues

        with open(env_example, "r") as f:
            env_vars = [
                line.split("=")[0].strip()
                for line in f
                if "=" in line and not line.strip().startswith("#")
            ]

        # Search for usage in code
        python_files = self.get_all_python_files("app")
        code_content = ""
        for file in python_files:
            try:
                with open(file, "r", encoding="utf-8") as f:
                    code_content += f.read() + "\n"
            except:
                pass

        for var in env_vars:
            if var not in code_content:
                issues.append(
                    {
                        "variable": var,
                        "type": "unused_env_var",
                        "severity": "LOW",
                        "reason": f"Environment variable {var} not found in codebase",
                    }
                )

        return issues

    def analyze_test_coverage(self) -> List[Dict]:
        """Find modules without corresponding tests"""
        issues = []

        # Get all services
        services = self.get_all_python_files("app/services")
        services = [s for s in services if s.name != "__init__.py"]

        # Get all test files
        tests = self.get_all_python_files("tests")
        test_names = {t.stem.replace("test_", "") for t in tests}

        for service in services:
            service_name = service.stem
            if service_name not in test_names:
                issues.append(
                    {
                        "file": str(service.relative_to(self.root)),
                        "type": "missing_test",
                        "severity": "MEDIUM",
                        "reason": f"No test file found for {service_name}",
                    }
                )

        return issues

    def run_full_audit(self) -> Dict:
        """Execute all audit checks"""
        print("🔍 Starting GridBot v2.5 Full Codebase Audit...")

        # Section 1: Unused Code
        print("\n📂 Section 1: Auditing Unused Code...")
        self.findings["unused_code"].extend(self.find_unused_services())
        self.findings["unused_code"].extend(self.find_unused_scripts())
        print(f"   Found {len(self.findings['unused_code'])} unused code items")

        # Section 2: Duplicate Code
        print("\n📄 Section 2: Auditing Duplicate Code...")
        self.findings["duplicate_code"].extend(self.find_duplicate_services())
        print(f"   Found {len(self.findings['duplicate_code'])} duplicate code items")

        # Section 3: Code Quality
        print("\n✨ Section 3: Auditing Code Quality...")
        self.findings["code_quality"].extend(self.find_missing_type_hints())
        print(f"   Found {len(self.findings['code_quality'])} code quality issues")

        # Section 4: Performance
        print("\n⚡ Section 4: Auditing Performance...")
        self.findings["performance"].extend(self.find_blocking_io_in_async())
        print(f"   Found {len(self.findings['performance'])} performance issues")

        # Section 6: Configuration
        print("\n⚙️ Section 6: Auditing Configuration...")
        self.findings["configuration"].extend(self.find_unused_env_vars())
        print(f"   Found {len(self.findings['configuration'])} configuration issues")

        # Section 7: Testing
        print("\n🧪 Section 7: Auditing Testing...")
        self.findings["testing"].extend(self.find_missing_tests())
        print(f"   Found {len(self.findings['testing'])} testing issues")

        # Calculate statistics
        self.stats["total_files_analyzed"] = len(self.get_all_python_files("app"))
        self.stats["services_count"] = len(self.get_all_python_files("app/services"))
        self.stats["scripts_count"] = len(self.get_all_python_files("scripts"))
        self.stats["tests_count"] = len(self.get_all_python_files("tests"))

        # Count severity levels
        summary = {
            "unused_files": len(
                [f for f in self.findings["unused_code"] if "file" in f]
            ),
            "duplicate_code_blocks": len(self.findings["duplicate_code"]),
            "optimization_opportunities": len(self.findings["performance"]),
            "code_quality_issues": len(self.findings["code_quality"]),
            "configuration_issues": len(self.findings["configuration"]),
            "test_coverage_gaps": len(self.findings["testing"]),
            "critical_count": sum(
                1
                for category in self.findings.values()
                for item in category
                if item.get("severity") == "CRITICAL"
            ),
            "high_count": sum(
                1
                for category in self.findings.values()
                for item in category
                if item.get("severity") == "HIGH"
            ),
            "medium_count": sum(
                1
                for category in self.findings.values()
                for item in category
                if item.get("severity") == "MEDIUM"
            ),
            "low_count": sum(
                1
                for category in self.findings.values()
                for item in category
                if item.get("severity") == "LOW"
            ),
        }

        return {
            "audit_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "gridbot_version": "2.5",
            "statistics": self.stats,
            "summary": summary,
            "findings": self.findings,
        }

    def find_missing_tests(self) -> List[Dict]:
        """Wrapper for analyze_test_coverage"""
        return self.analyze_test_coverage()


def main():
    root_path = "/path/to/gridbot"
    auditor = GridBotAuditor(root_path)

    report = auditor.run_full_audit()

    # Save JSON report
    reports_dir = Path(root_path) / "reports" / "audits"
    reports_dir.mkdir(parents=True, exist_ok=True)

    json_path = reports_dir / "code_audit_report_20260104.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Audit complete! Report saved to: {json_path}")
    print("\n📊 Summary:")
    print(f"   - Unused files: {report['summary']['unused_files']}")
    print(f"   - Duplicate code: {report['summary']['duplicate_code_blocks']}")
    print(f"   - Performance issues: {report['summary']['optimization_opportunities']}")
    print(f"   - Quality issues: {report['summary']['code_quality_issues']}")
    print(f"   - Config issues: {report['summary']['configuration_issues']}")
    print(f"   - Test gaps: {report['summary']['test_coverage_gaps']}")
    print("\n🚨 Severity Breakdown:")
    print(f"   - CRITICAL: {report['summary']['critical_count']}")
    print(f"   - HIGH: {report['summary']['high_count']}")
    print(f"   - MEDIUM: {report['summary']['medium_count']}")
    print(f"   - LOW: {report['summary']['low_count']}")


if __name__ == "__main__":
    main()
