"""
Balance Comparison Tool - GridBot v2.5
Compara balances en tiempo real con granularidad por asset

Ejecutar: python scripts/balance_comparison.py --continuous --interval 30
"""

import asyncio
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from dotenv import load_dotenv

load_dotenv()

from app.services.binance_client_singleton import get_binance_client_singleton

logging.basicConfig(level=logging.WARNING)  # Solo warnings
logger = logging.getLogger(__name__)

console = Console()


class BalanceComparator:
    """Comparador de balances en tiempo real"""

    def __init__(self):
        self.client = get_binance_client_singleton()
        self.history: List[Dict] = []
        self.initial_snapshot = None

    async def get_current_balances(self) -> Dict[str, any]:
        """Obtiene balances actuales de Binance"""
        try:
            account_info = self.client.client.get_account()

            balances = {}
            total_value_usdt = Decimal("0")
            usdt_balance = Decimal("0")

            for balance in account_info.get("balances", []):
                asset = balance["asset"]
                free = Decimal(str(balance["free"]))
                locked = Decimal(str(balance["locked"]))
                total = free + locked

                if total > 0:
                    value_usdt = Decimal("0")
                    price = Decimal("0")

                    if asset == "USDT":
                        usdt_balance = total
                        value_usdt = total
                    else:
                        try:
                            symbol = f"{asset}USDT"
                            ticker = self.client.client.get_symbol_ticker(symbol=symbol)
                            price = Decimal(str(ticker["price"]))
                            value_usdt = total * price
                        except:
                            pass

                    total_value_usdt += value_usdt

                    balances[asset] = {
                        "free": free,
                        "locked": locked,
                        "total": total,
                        "price": price,
                        "value_usdt": value_usdt,
                    }

            return {
                "timestamp": datetime.now(timezone.utc),
                "balances": balances,
                "total_value_usdt": total_value_usdt,
                "usdt_balance": usdt_balance,
            }
        except Exception as e:
            logger.error(f"Error obteniendo balances: {e}")
            return None

    def compare_snapshots(self, prev: Dict, curr: Dict) -> Dict:
        """Compara dos snapshots y calcula diferencias"""
        if not prev or not curr:
            return {}

        prev_balances = prev["balances"]
        curr_balances = curr["balances"]

        changes = {}

        # Comparar assets existentes
        all_assets = set(prev_balances.keys()) | set(curr_balances.keys())

        for asset in all_assets:
            prev_data = prev_balances.get(asset, {})
            curr_data = curr_balances.get(asset, {})

            prev_total = prev_data.get("total", Decimal("0"))
            curr_total = curr_data.get("total", Decimal("0"))

            prev_value = prev_data.get("value_usdt", Decimal("0"))
            curr_value = curr_data.get("value_usdt", Decimal("0"))

            diff_quantity = curr_total - prev_total
            diff_value = curr_value - prev_value

            if diff_quantity != 0 or diff_value != 0:
                changes[asset] = {
                    "prev_quantity": prev_total,
                    "curr_quantity": curr_total,
                    "diff_quantity": diff_quantity,
                    "prev_value_usdt": prev_value,
                    "curr_value_usdt": curr_value,
                    "diff_value_usdt": diff_value,
                    "change_pct": float(
                        (diff_value / prev_value * 100) if prev_value > 0 else 0
                    ),
                }

        total_diff = curr["total_value_usdt"] - prev["total_value_usdt"]

        return {
            "timestamp": curr["timestamp"],
            "duration_seconds": (curr["timestamp"] - prev["timestamp"]).total_seconds(),
            "changes": changes,
            "total_value_change": total_diff,
            "total_value_change_pct": float(
                (total_diff / prev["total_value_usdt"] * 100)
                if prev["total_value_usdt"] > 0
                else 0
            ),
        }

    def create_balance_table(self, snapshot: Dict) -> Table:
        """Crea tabla rica de balances"""
        table = Table(
            title=f"💰 Balances - {snapshot['timestamp'].strftime('%H:%M:%S')}",
            box=box.ROUNDED,
        )

        table.add_column("Asset", style="cyan", no_wrap=True)
        table.add_column("Free", justify="right", style="green")
        table.add_column("Locked", justify="right", style="yellow")
        table.add_column("Total", justify="right", style="bold")
        table.add_column("Price USDT", justify="right")
        table.add_column("Value USDT", justify="right", style="bold magenta")

        balances = snapshot["balances"]

        # Ordenar por valor
        sorted_balances = sorted(
            balances.items(), key=lambda x: float(x[1]["value_usdt"]), reverse=True
        )

        for asset, data in sorted_balances:
            table.add_row(
                asset,
                f"{float(data['free']):.8f}",
                f"{float(data['locked']):.8f}",
                f"{float(data['total']):.8f}",
                f"{float(data['price']):.8f}" if data["price"] > 0 else "-",
                f"${float(data['value_usdt']):.2f}",
            )

        # Totales
        table.add_row(
            "TOTAL",
            "",
            "",
            "",
            "",
            f"${float(snapshot['total_value_usdt']):.2f}",
            style="bold white on blue",
        )

        return table

    def create_changes_table(self, comparison: Dict) -> Table:
        """Crea tabla de cambios"""
        if not comparison or "changes" not in comparison:
            return None

        changes = comparison["changes"]

        if not changes:
            return Panel(
                "[green]✅ No hay cambios desde el último snapshot[/green]",
                title="Cambios",
                box=box.ROUNDED,
            )

        table = Table(
            title=f"📊 Cambios en {comparison['duration_seconds']:.0f}s",
            box=box.ROUNDED,
        )

        table.add_column("Asset", style="cyan")
        table.add_column("Δ Cantidad", justify="right")
        table.add_column("Δ Valor USDT", justify="right")
        table.add_column("Δ %", justify="right")

        for asset, data in changes.items():
            diff_qty = data["diff_quantity"]
            diff_val = data["diff_value_usdt"]
            change_pct = data["change_pct"]

            qty_style = "green" if diff_qty > 0 else "red" if diff_qty < 0 else "white"
            val_style = "green" if diff_val > 0 else "red" if diff_val < 0 else "white"

            table.add_row(
                asset,
                f"[{qty_style}]{float(diff_qty):+.8f}[/{qty_style}]",
                f"[{val_style}]${float(diff_val):+.2f}[/{val_style}]",
                f"[{val_style}]{change_pct:+.2f}%[/{val_style}]",
            )

        # Total
        total_diff = comparison["total_value_change"]
        total_pct = comparison["total_value_change_pct"]
        style = "green" if total_diff > 0 else "red" if total_diff < 0 else "white"

        table.add_row(
            "TOTAL",
            "",
            f"[bold {style}]${float(total_diff):+.2f}[/bold {style}]",
            f"[bold {style}]{total_pct:+.2f}%[/bold {style}]",
            style=f"bold {style}",
        )

        return table

    async def monitor_continuous(self, interval_seconds: int = 30):
        """Monitorea balances continuamente"""
        console.print(
            "\n[bold cyan]🔍 Iniciando monitoreo continuo de balances...[/bold cyan]\n"
        )

        prev_snapshot = await self.get_current_balances()
        if not prev_snapshot:
            console.print("[red]❌ Error obteniendo snapshot inicial[/red]")
            return

        self.initial_snapshot = prev_snapshot
        console.print(self.create_balance_table(prev_snapshot))
        console.print(
            f"\n[yellow]⏳ Esperando {interval_seconds}s para siguiente snapshot...[/yellow]\n"
        )

        iteration = 1

        try:
            while True:
                await asyncio.sleep(interval_seconds)

                curr_snapshot = await self.get_current_balances()
                if not curr_snapshot:
                    console.print("[red]❌ Error obteniendo snapshot[/red]")
                    continue

                comparison = self.compare_snapshots(prev_snapshot, curr_snapshot)

                # Limpiar consola
                console.clear()

                # Mostrar header
                console.print(
                    f"\n[bold cyan]═══ MONITOREO DE BALANCES #{iteration} ═══[/bold cyan]\n"
                )

                # Mostrar balances actuales
                console.print(self.create_balance_table(curr_snapshot))
                console.print()

                # Mostrar cambios
                changes_display = self.create_changes_table(comparison)
                if changes_display:
                    console.print(changes_display)
                    console.print()

                # Mostrar cambio total desde inicio
                initial_diff = float(
                    curr_snapshot["total_value_usdt"]
                    - self.initial_snapshot["total_value_usdt"]
                )
                initial_pct = (
                    (
                        initial_diff
                        / float(self.initial_snapshot["total_value_usdt"])
                        * 100
                    )
                    if self.initial_snapshot["total_value_usdt"] > 0
                    else 0
                )

                style = (
                    "green"
                    if initial_diff > 0
                    else "red"
                    if initial_diff < 0
                    else "white"
                )
                console.print(
                    Panel(
                        f"[bold]Valor inicial:[/bold] ${float(self.initial_snapshot['total_value_usdt']):.2f}\n"
                        f"[bold]Valor actual:[/bold] ${float(curr_snapshot['total_value_usdt']):.2f}\n"
                        f"[bold {style}]Cambio total:[/bold {style}] [{style}]${initial_diff:+.2f} ({initial_pct:+.2f}%)[/{style}]",
                        title="📈 Desde Inicio",
                        box=box.DOUBLE,
                    )
                )

                console.print(
                    f"\n[dim]Próxima actualización en {interval_seconds}s... (Ctrl+C para detener)[/dim]\n"
                )

                prev_snapshot = curr_snapshot
                self.history.append(comparison)
                iteration += 1

        except KeyboardInterrupt:
            console.print("\n[yellow]⏹️  Monitoreo detenido por usuario[/yellow]")
            self._show_summary()

    def _show_summary(self):
        """Muestra resumen de la sesión"""
        if not self.history:
            return

        console.print("\n[bold cyan]═══ RESUMEN DE SESIÓN ═══[/bold cyan]\n")

        total_changes = len([h for h in self.history if h.get("changes")])
        total_duration = sum(h.get("duration_seconds", 0) for h in self.history)

        console.print(f"📊 Total de snapshots: {len(self.history)}")
        console.print(
            f"⏱️  Duración total: {total_duration:.0f}s ({total_duration/60:.1f}min)"
        )
        console.print(f"🔄 Cambios detectados: {total_changes}")

        console.print("\n[green]✅ Sesión finalizada[/green]\n")


async def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Comparación de Balances en Tiempo Real"
    )
    parser.add_argument("--continuous", action="store_true", help="Monitoreo continuo")
    parser.add_argument(
        "--interval", type=int, default=30, help="Intervalo en segundos (default: 30)"
    )
    parser.add_argument("--snapshot", action="store_true", help="Un solo snapshot")

    args = parser.parse_args()

    comparator = BalanceComparator()

    if args.continuous:
        await comparator.monitor_continuous(args.interval)
    else:
        # Snapshot único
        snapshot = await comparator.get_current_balances()
        if snapshot:
            console.print(comparator.create_balance_table(snapshot))
        else:
            console.print("[red]❌ Error obteniendo snapshot[/red]")


if __name__ == "__main__":
    # Instalar rich si no está: pip install rich
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[yellow]👋 Adiós[/yellow]")
