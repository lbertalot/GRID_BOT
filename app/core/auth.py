from fastapi import HTTPException, Depends, Request
import os


def get_api_key(request: Request) -> str:
    """
    Valida el API key en el header Authorization con formato Bearer.
    Devuelve 401 para ausente/malformado/inválido (tests esperan 401).
    """
    header = request.headers.get("Authorization")
    if not header:
        raise HTTPException(status_code=401, detail="Falta Authorization")
    if not header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Formato Authorization inválido")
    token = header.split(" ", 1)[1].strip()
    valid_api_key = os.getenv("API_KEY")
    if not valid_api_key:
        raise HTTPException(
            status_code=500,
            detail="API_KEY no configurado en el servidor — revisar .env",
        )
    if token != valid_api_key:
        raise HTTPException(status_code=401, detail="API key inválido")
    return token


def require_auth(api_key: str = Depends(get_api_key)) -> str:
    """
    Dependencia para endpoints que requieren autenticación.
    """
    return api_key


# Backwards-compatible alias expected by tests and routes
get_api_key_user = require_auth
