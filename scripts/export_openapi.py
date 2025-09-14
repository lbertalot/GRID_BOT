import json
from pathlib import Path
from fastapi.openapi.utils import get_openapi
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
