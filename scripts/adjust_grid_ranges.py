#!/usr/bin/env python3
"""
Ajusta dinámicamente los rangos de grid_config_optimized.json a precio de mercado ±5%.
Usa el wrapper asíncrono AsyncBinanceWrapper para no bloquear.
"""

import asyncio
import json
from pathlib import Path
from typing import Dict

from app.services.binance_async import AsyncBinanceWrapper


CONFIG_PATH = Path("grid_config_optimized.json")


async def main() -> None:
    if not CONFIG_PATH.exists():
        raise SystemExit("grid_config_optimized.json no encontrado")

    data: Dict[str, Dict] = json.loads(CONFIG_PATH.read_text())

    wrapper = AsyncBinanceWrapper(ttl_seconds=2)

    async def update_symbol(sym: str) -> None:
        price = await wrapper.get_price(sym)
        if price and price > 0:
            # ±5%
            min_price = round(price * 0.95, 6)
            max_price = round(price * 1.05, 6)
            entry = data.get(sym, {})
            entry["min_price"] = min_price
            entry["max_price"] = max_price
            entry["symbol"] = sym
            # mantener grids y quantity existentes
            data[sym] = entry

    symbols = [s for s in data.keys() if s != "_optimization_metadata"]
    await asyncio.gather(*(update_symbol(s) for s in symbols))

    # Actualizar metadata
    from datetime import datetime
    data.setdefault("_optimization_metadata", {})
    data["_optimization_metadata"]["optimized_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data["_optimization_metadata"]["optimization_version"] = "auto-range-±5%"

    CONFIG_PATH.write_text(json.dumps(data, indent=2))
    print("Rangos actualizados a ±5% del precio de mercado para:", symbols)


if __name__ == "__main__":
    asyncio.run(main())


