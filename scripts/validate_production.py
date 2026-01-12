#!/usr/bin/env python3
"""
GridBot v2.5 - Script de Validación en Producción
Valida que los fixes de Bugs #1, #2 y #3 funcionan correctamente.
"""
import sys
import time
import requests
import subprocess
import json
from typing import Dict, List, Tuple
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

console = Console()

# Configuración
API_URL = "http://localhost:8000"
PROMETHEUS_URL = "http://localhost:9090"
REDIS_CONTAINER = "gridbot_redis"
DB_CONTAINER = "gridbot_db"
API_CONTAINER = "gridbot_api"
WORKER_CONTAINER = "gridbot_celery_worker"


def print_header(title: str):
    """Imprime un header bonito."""
    console.print()
    console.print(Panel(f"[bold cyan]{title}[/bold cyan]", box=box.DOUBLE))
    console.print()


def run_command(cmd: List[str]) -> Tuple[bool, str]:
    """Ejecuta un comando y retorna (success, output)."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.returncode == 0, result.stdout + result.stderr
    except Exception as e:
        return False, str(e)


def check_service_health() -> Dict[str, bool]:
    """Verifica que todos los servicios estén up."""
    print_header("🔍 VERIFICACIÓN DE SERVICIOS")
    
    services = {
        "API": False,
        "Redis": False,
        "PostgreSQL": False,
        "Prometheus": False,
        "Celery Worker": False
    }
    
    # API Health
    try:
        resp = requests.get(f"{API_URL}/health", timeout=5)
        services["API"] = resp.status_code == 200
        console.print(f"✅ API: {resp.json().get('status', 'unknown')}")
    except Exception as e:
        console.print(f"❌ API: {e}")
    
    # Redis
    success, output = run_command([
        "docker", "exec", REDIS_CONTAINER, 
        "redis-cli", "ping"
    ])
    services["Redis"] = success and "PONG" in output
    console.print(f"{'✅' if services['Redis'] else '❌'} Redis: {'Connected' if services['Redis'] else 'Failed'}")
    
    # PostgreSQL
    success, output = run_command([
        "docker", "exec", DB_CONTAINER,
        "pg_isready", "-U", "griduser"
    ])
    services["PostgreSQL"] = success
    console.print(f"{'✅' if services['PostgreSQL'] else '❌'} PostgreSQL: {'Connected' if services['PostgreSQL'] else 'Failed'}")
    
    # Prometheus
    try:
        resp = requests.get(f"{PROMETHEUS_URL}/-/healthy", timeout=5)
        services["Prometheus"] = resp.status_code == 200
        console.print(f"✅ Prometheus: Healthy")
    except Exception as e:
        console.print(f"❌ Prometheus: {e}")
    
    # Celery Worker
    success, output = run_command([
        "docker", "logs", WORKER_CONTAINER, "--tail", "10"
    ])
    services["Celery Worker"] = success and "ready" in output.lower()
    console.print(f"{'✅' if services['Celery Worker'] else '❌'} Celery Worker: {'Running' if services['Celery Worker'] else 'Failed'}")
    
    return services


def validate_bug1_optimistic_locking() -> Dict[str, any]:
    """Valida Bug #1: Optimistic Locking."""
    print_header("🐛 BUG #1: OPTIMISTIC LOCKING")
    
    results = {
        "version_column_exists": False,
        "metric_exists": False,
        "conflicts_count": 0,
        "status": "UNKNOWN"
    }
    
    # 1. Verificar columna version
    console.print("[cyan]Verificando columna 'version' en tabla balances...[/cyan]")
    success, output = run_command([
        "docker", "exec", DB_CONTAINER,
        "psql", "-U", "griduser", "-d", "gridbot", "-c",
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'balances' AND column_name = 'version';"
    ])
    
    if success and "version" in output:
        results["version_column_exists"] = True
        console.print("✅ Columna 'version' existe")
    else:
        console.print("❌ Columna 'version' NO existe")
        results["status"] = "FAILED"
        return results
    
    # 2. Verificar métrica
    console.print("[cyan]Verificando métrica balance_update_conflicts_total...[/cyan]")
    try:
        resp = requests.get(f"{API_URL}/metrics", timeout=5)
        if resp.status_code == 200:
            metrics_text = resp.text
            if "balance_update_conflicts_total" in metrics_text:
                results["metric_exists"] = True
                console.print("✅ Métrica 'balance_update_conflicts_total' existe")
                
                # Parsear valor
                for line in metrics_text.split('\n'):
                    if line.startswith("balance_update_conflicts_total") and not line.startswith("#"):
                        try:
                            results["conflicts_count"] = int(float(line.split()[-1]))
                            console.print(f"   Conflictos totales: {results['conflicts_count']}")
                        except:
                            pass
            else:
                console.print("❌ Métrica NO existe")
    except Exception as e:
        console.print(f"❌ Error obteniendo métricas: {e}")
    
    # 3. Verificar balances
    console.print("[cyan]Verificando registros de balances...[/cyan]")
    success, output = run_command([
        "docker", "exec", DB_CONTAINER,
        "psql", "-U", "griduser", "-d", "gridbot", "-c",
        "SELECT asset, amount, version FROM balances LIMIT 5;"
    ])
    
    if success and "USDT" in output:
        console.print("✅ Balances con versión encontrados")
        console.print(f"   {output[:200]}...")
    
    # Conclusión
    if results["version_column_exists"] and results["metric_exists"]:
        results["status"] = "PASSED"
        console.print(Panel("[bold green]✅ Bug #1 VALIDADO[/bold green]", style="green"))
    else:
        results["status"] = "FAILED"
        console.print(Panel("[bold red]❌ Bug #1 FALLIDO[/bold red]", style="red"))
    
    return results


def validate_bug2_distributed_lock() -> Dict[str, any]:
    """Valida Bug #2: Lock Distribuido."""
    print_header("🐛 BUG #2: LOCK DISTRIBUIDO")
    
    results = {
        "locks_in_redis": False,
        "metrics_exist": False,
        "acquired_count": 0,
        "skipped_count": 0,
        "status": "UNKNOWN"
    }
    
    # 1. Verificar locks en Redis
    console.print("[cyan]Verificando locks en Redis...[/cyan]")
    success, output = run_command([
        "docker", "exec", REDIS_CONTAINER,
        "redis-cli", "KEYS", "lock:*"
    ])
    
    if success:
        locks = [l.strip() for l in output.strip().split('\n') if l.strip()]
        if locks and locks[0] != "(empty array)":
            results["locks_in_redis"] = True
            console.print(f"✅ {len(locks)} lock(s) encontrado(s): {locks}")
        else:
            console.print("⚠️  No hay locks activos actualmente (puede ser normal si no hay tasks corriendo)")
    else:
        console.print(f"❌ Error consultando Redis: {output}")
    
    # 2. Verificar métricas
    console.print("[cyan]Verificando métricas de locks...[/cyan]")
    try:
        resp = requests.get(f"{API_URL}/metrics", timeout=5)
        if resp.status_code == 200:
            metrics_text = resp.text
            
            # distributed_lock_acquired_total
            if "distributed_lock_acquired_total" in metrics_text:
                results["metrics_exist"] = True
                console.print("✅ Métricas de lock distribuido existen")
                
                for line in metrics_text.split('\n'):
                    if line.startswith("distributed_lock_acquired_total") and not line.startswith("#"):
                        try:
                            results["acquired_count"] += int(float(line.split()[-1]))
                        except:
                            pass
                    
                    if line.startswith("distributed_lock_skipped_total") and not line.startswith("#"):
                        try:
                            results["skipped_count"] += int(float(line.split()[-1]))
                        except:
                            pass
                
                console.print(f"   Locks adquiridos: {results['acquired_count']}")
                console.print(f"   Locks omitidos: {results['skipped_count']}")
                
                if results["acquired_count"] > 0:
                    skip_rate = (results["skipped_count"] / results["acquired_count"]) * 100
                    console.print(f"   Tasa de omisión: {skip_rate:.2f}%")
                    
                    if skip_rate < 5:
                        console.print(f"   ✅ Tasa de omisión < 5% (óptimo)")
                    else:
                        console.print(f"   ⚠️  Tasa de omisión > 5% (revisar)")
            else:
                console.print("❌ Métricas de lock NO existen")
    except Exception as e:
        console.print(f"❌ Error obteniendo métricas: {e}")
    
    # 3. Verificar logs
    console.print("[cyan]Verificando logs de locks en Celery Worker...[/cyan]")
    success, output = run_command([
        "docker", "logs", WORKER_CONTAINER, "--tail", "100"
    ])
    
    if success:
        lock_acquired = output.count("Lock") + output.count("lock")
        console.print(f"   {lock_acquired} referencias a 'lock' en últimos 100 logs")
    
    # Conclusión
    if results["metrics_exist"] and (results["acquired_count"] > 0 or not results["locks_in_redis"]):
        results["status"] = "PASSED"
        console.print(Panel("[bold green]✅ Bug #2 VALIDADO[/bold green]", style="green"))
    else:
        results["status"] = "WARNING"
        console.print(Panel("[bold yellow]⚠️  Bug #2 - Requiere más tiempo de monitoreo[/bold yellow]", style="yellow"))
    
    return results


def validate_bug3_async_io() -> Dict[str, any]:
    """Valida Bug #3: Async I/O."""
    print_header("🐛 BUG #3: ASYNC I/O")
    
    results = {
        "latency_p50": 0,
        "latency_p99": 0,
        "throughput": 0,
        "no_blocking": False,
        "status": "UNKNOWN"
    }
    
    # 1. Test de latencia simple
    console.print("[cyan]Midiendo latencia de /health...[/cyan]")
    latencies = []
    
    for i in range(10):
        try:
            start = time.time()
            resp = requests.get(f"{API_URL}/health", timeout=5)
            elapsed = (time.time() - start) * 1000  # ms
            latencies.append(elapsed)
        except Exception as e:
            console.print(f"   ⚠️  Request {i+1} falló: {e}")
    
    if latencies:
        latencies.sort()
        p50_idx = len(latencies) // 2
        p99_idx = int(len(latencies) * 0.99)
        
        results["latency_p50"] = latencies[p50_idx]
        results["latency_p99"] = latencies[p99_idx] if p99_idx < len(latencies) else latencies[-1]
        
        console.print(f"   P50 latency: {results['latency_p50']:.2f}ms")
        console.print(f"   P99 latency: {results['latency_p99']:.2f}ms")
        
        if results["latency_p50"] < 50:
            console.print("   ✅ P50 < 50ms (excelente)")
        elif results["latency_p50"] < 100:
            console.print("   ✅ P50 < 100ms (bueno)")
        else:
            console.print("   ⚠️  P50 > 100ms (revisar)")
    
    # 2. Test de concurrencia (simple)
    console.print("[cyan]Test de concurrencia (3 requests paralelos)...[/cyan]")
    start = time.time()
    
    # Simulamos concurrencia con threads
    import threading
    
    def make_request():
        try:
            requests.get(f"{API_URL}/health", timeout=5)
        except:
            pass
    
    threads = []
    for _ in range(3):
        t = threading.Thread(target=make_request)
        threads.append(t)
        t.start()
    
    for t in threads:
        t.join()
    
    concurrent_time = (time.time() - start) * 1000  # ms
    console.print(f"   3 requests concurrentes: {concurrent_time:.2f}ms")
    
    # Ratio vs secuencial
    if latencies:
        sequential_time = sum(latencies[:3])
        ratio = concurrent_time / (sequential_time / 3)
        console.print(f"   Ratio concurrente/secuencial: {ratio:.2f}x")
        
        if ratio < 3:
            results["no_blocking"] = True
            console.print("   ✅ Event loop NO bloqueado (ratio < 3x)")
        else:
            console.print("   ⚠️  Posible bloqueo (ratio >= 3x)")
    
    # 3. Verificar métricas de Prometheus
    console.print("[cyan]Verificando métricas de latencia en Prometheus...[/cyan]")
    try:
        # Query P99 latency
        query = 'histogram_quantile(0.99, rate(api_request_duration_seconds_bucket[5m]))'
        resp = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query",
            params={"query": query},
            timeout=5
        )
        
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == "success":
                result_value = data.get("data", {}).get("result", [])
                if result_value:
                    p99_seconds = float(result_value[0]["value"][1])
                    p99_ms = p99_seconds * 1000
                    console.print(f"   P99 latency (Prometheus): {p99_ms:.2f}ms")
                    
                    if p99_ms < 250:
                        console.print("   ✅ P99 < 250ms (objetivo cumplido)")
                else:
                    console.print("   ⚠️  No hay datos suficientes en Prometheus")
    except Exception as e:
        console.print(f"   ⚠️  Error consultando Prometheus: {e}")
    
    # Conclusión
    if results["latency_p50"] < 100 and results["no_blocking"]:
        results["status"] = "PASSED"
        console.print(Panel("[bold green]✅ Bug #3 VALIDADO[/bold green]", style="green"))
    elif results["latency_p50"] < 200:
        results["status"] = "WARNING"
        console.print(Panel("[bold yellow]⚠️  Bug #3 - Performance aceptable[/bold yellow]", style="yellow"))
    else:
        results["status"] = "FAILED"
        console.print(Panel("[bold red]❌ Bug #3 FALLIDO[/bold red]", style="red"))
    
    return results


def generate_summary_report(
    services: Dict[str, bool],
    bug1: Dict,
    bug2: Dict,
    bug3: Dict
):
    """Genera un reporte resumen."""
    print_header("📊 RESUMEN DE VALIDACIÓN")
    
    # Tabla de servicios
    table_services = Table(title="Estado de Servicios", box=box.ROUNDED)
    table_services.add_column("Servicio", style="cyan")
    table_services.add_column("Estado", style="bold")
    
    for service, status in services.items():
        status_text = "✅ OK" if status else "❌ FAILED"
        table_services.add_row(service, status_text)
    
    console.print(table_services)
    console.print()
    
    # Tabla de bugs
    table_bugs = Table(title="Validación de Bugs", box=box.ROUNDED)
    table_bugs.add_column("Bug", style="cyan")
    table_bugs.add_column("Status", style="bold")
    table_bugs.add_column("Detalles")
    
    # Bug #1
    status_emoji = {
        "PASSED": "✅",
        "WARNING": "⚠️",
        "FAILED": "❌",
        "UNKNOWN": "❓"
    }
    
    table_bugs.add_row(
        "Bug #1: Optimistic Locking",
        f"{status_emoji.get(bug1['status'], '❓')} {bug1['status']}",
        f"Conflictos: {bug1['conflicts_count']}"
    )
    
    table_bugs.add_row(
        "Bug #2: Lock Distribuido",
        f"{status_emoji.get(bug2['status'], '❓')} {bug2['status']}",
        f"Adquiridos: {bug2['acquired_count']}, Omitidos: {bug2['skipped_count']}"
    )
    
    table_bugs.add_row(
        "Bug #3: Async I/O",
        f"{status_emoji.get(bug3['status'], '❓')} {bug3['status']}",
        f"P50: {bug3['latency_p50']:.1f}ms, P99: {bug3['latency_p99']:.1f}ms"
    )
    
    console.print(table_bugs)
    console.print()
    
    # Conclusión general
    all_services_ok = all(services.values())
    all_bugs_passed = all([
        bug1["status"] in ["PASSED", "WARNING"],
        bug2["status"] in ["PASSED", "WARNING"],
        bug3["status"] in ["PASSED", "WARNING"]
    ])
    
    if all_services_ok and all_bugs_passed:
        console.print(Panel(
            "[bold green]✅ VALIDACIÓN EXITOSA[/bold green]\n\n"
            "El sistema está funcionando correctamente.\n"
            "Se recomienda monitoreo continuo por 24-48h antes de Bug #4.",
            style="green",
            box=box.DOUBLE
        ))
        return True
    else:
        console.print(Panel(
            "[bold yellow]⚠️  VALIDACIÓN PARCIAL[/bold yellow]\n\n"
            "Algunos aspectos requieren revisión.\n"
            "Ver detalles arriba.",
            style="yellow",
            box=box.DOUBLE
        ))
        return False


def main():
    """Función principal."""
    console.print()
    console.print(Panel(
        "[bold cyan]GridBot v2.5 - Validación en Producción[/bold cyan]\n\n"
        "Este script valida que los fixes de Bugs #1, #2 y #3 funcionan correctamente.",
        box=box.DOUBLE
    ))
    console.print()
    
    # 1. Verificar servicios
    services = check_service_health()
    
    if not all(services.values()):
        console.print()
        console.print(Panel(
            "[bold red]❌ ERROR[/bold red]\n\n"
            "No todos los servicios están operativos.\n"
            "Por favor, verifica el estado de los contenedores.",
            style="red"
        ))
        sys.exit(1)
    
    # 2. Validar bugs
    bug1_results = validate_bug1_optimistic_locking()
    bug2_results = validate_bug2_distributed_lock()
    bug3_results = validate_bug3_async_io()
    
    # 3. Generar reporte
    success = generate_summary_report(services, bug1_results, bug2_results, bug3_results)
    
    # 4. Guardar reporte
    report = {
        "timestamp": datetime.now().isoformat(),
        "services": services,
        "bug1": bug1_results,
        "bug2": bug2_results,
        "bug3": bug3_results,
        "overall_status": "PASSED" if success else "WARNING"
    }
    
    report_file = f"validation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, "w") as f:
        json.dump(report, f, indent=2)
    
    console.print()
    console.print(f"📝 Reporte guardado en: [cyan]{report_file}[/cyan]")
    console.print()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

