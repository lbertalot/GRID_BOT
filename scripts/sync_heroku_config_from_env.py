#!/usr/bin/env python3
"""
Sincroniza variables de .env a Heroku config (sin imprimir valores).
Uso: python scripts/sync_heroku_config_from_env.py [app_name]

- REDIS_URL, CELERY_BROKER_URL y CELERY_RESULT_BACKEND no se sincronizan:
  en producción Heroku las provee el addon heroku-redis; sobrescribirlas
  con valores locales (p. ej. redis://localhost) rompe el worker.
- DATABASE_URL sí se puede sincronizar si usas Neon/Upstash (pon las URLs en .env).
"""
import os
import subprocess
import sys
from pathlib import Path

# Cargar .env manualmente sin imprimir valores
def load_env(env_path: Path) -> dict[str, str]:
    out = {}
    if not env_path.exists():
        return out
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip()
            if not k:
                continue
            v = v.strip('"').strip("'")
            if "YOUR_" in v or "_HERE" in v or v in ("", "your_email@gmail.com", "your_app_password", "noreply@gridbot.com"):
                continue
            out[k] = v
    return out

def main():
    app = sys.argv[1] if len(sys.argv) > 1 else "grid-bot-ia"
    root = Path(__file__).resolve().parent.parent
    env_path = root / ".env"
    env = load_env(env_path)
    if not env:
        print("No variables to set (or .env missing/empty).")
        return 1
    # No sobrescribir Redis en Heroku: el addon inyecta REDIS_URL (y Celery la usa).
    exclude = {"REDIS_URL", "CELERY_BROKER_URL", "CELERY_RESULT_BACKEND"}
    for k, v in env.items():
        if k in exclude:
            print(f"Skip {k} (managed by Heroku Redis addon)")
            continue
        if not v:
            continue
        r = subprocess.run(
            ["heroku", "config:set", f"{k}={v}", "-a", app],
            capture_output=True,
            text=True,
            cwd=root,
        )
        if r.returncode != 0:
            print(f"Error setting {k}: {r.stderr or r.stdout}")
        else:
            print(f"Set {k}")
    print("Done.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
