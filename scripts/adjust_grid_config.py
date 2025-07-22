import os
import sys
import json
from datetime import datetime

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from binance.client import Client
from dotenv import load_dotenv

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

def adjust_grid_config(
    config_filename: str = "grid_config_optimized.json",
    percentage_range: float = 2.0,
):
    """
    Adjusts the grid configuration price ranges based on current market prices
    and overwrites the original file.
    """
    config_file_path = os.path.join(PROJECT_ROOT, config_filename)
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

    print(f"Ajustando y sobreescribiendo '{config_file_path}' con un rango de +/- {percentage_range}%.")

    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_API_SECRET")

    if not api_key or not api_secret:
        print("Error: Credenciales de Binance no encontradas en el archivo .env.")
        return

    try:
        client = Client(api_key, api_secret)
        with open(config_file_path, "r") as f:
            config = json.load(f)

        print("Configuración actual cargada. Obteniendo precios de mercado...")

        for symbol in config:
            if symbol.startswith("_"):
                continue

            try:
                ticker = client.get_symbol_ticker(symbol=symbol)
                current_price = float(ticker["price"])

                # Calculate new price range
                price_change = current_price * (percentage_range / 100)
                new_min_price = current_price - price_change
                new_max_price = current_price + price_change

                print(
                    f"  - {symbol}: Precio actual ${current_price:.4f} -> Nuevo rango "
                    f"(${new_min_price:.4f} - ${new_max_price:.4f})"
                )

                # Update config
                config[symbol]["min_price"] = new_min_price
                config[symbol]["max_price"] = new_max_price
                config[symbol]["last_action"] = None # Reset last action

            except Exception as e:
                print(f"  - Error obteniendo el precio para {symbol}: {e}. Se mantendrá la configuración actual.")

        # Update metadata
        config["_optimization_metadata"] = {
            "optimized_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "optimization_version": "5.0",
            "ajuste_tipo": f"Rangos ajustados a precios actuales con un {percentage_range}% de margen.",
        }

        # Write to the original file
        with open(config_file_path, "w") as f:
            json.dump(config, f, indent=2)

        print(f"\n✅ ¡Configuración '{config_filename}' actualizada con éxito!")

    except FileNotFoundError:
        print(f"Error: El archivo de configuración '{config_file_path}' no fue encontrado.")
    except Exception as e:
        print(f"Ocurrió un error inesperado: {e}")


if __name__ == "__main__":
    adjust_grid_config() 