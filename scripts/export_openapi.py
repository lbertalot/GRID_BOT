import json
import sys
from pathlib import Path
from fastapi.openapi.utils import get_openapi

# Asegurar que la raíz del repo esté en PYTHONPATH
THIS_DIR = Path(__file__).resolve().parent
ROOT = THIS_DIR.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.main import app


def main() -> None:
    schema = get_openapi(
        title=app.title,
        version=app.version,
        routes=app.routes,
        description=app.description,
    )
    out_path = Path(__file__).resolve().parents[1] / "Docs" / "openapi.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(schema, f, ensure_ascii=False, indent=2)
    print(f"OpenAPI exportado a {out_path}")


if __name__ == "__main__":
    main()
