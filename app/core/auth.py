from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import os
from typing import Optional

security = HTTPBearer()

def get_api_key(credentials: HTTPAuthorizationCredentials = Security(security)) -> str:
    """
    Valida el API key proporcionado en el header Authorization.
    Retorna el API key si es válido, sino lanza HTTPException.
    """
    api_key = credentials.credentials
    valid_api_key = os.getenv("API_KEY")
    
    if not valid_api_key:
        raise HTTPException(
            status_code=500, 
            detail="API key no configurado en el servidor"
        )
    
    if api_key != valid_api_key:
        raise HTTPException(
            status_code=401, 
            detail="API key inválido"
        )
    
    return api_key

def require_auth(api_key: str = Depends(get_api_key)) -> str:
    """
    Dependencia para endpoints que requieren autenticación.
    """
    return api_key 