"""
Tests P1 (FASE 3) — app/core/auth.py
─────────────────────────────────────────────────────────────────
Objetivo: subir cobertura de 32% → ≥95% (TESTING_RULES.md §3).

Cubre:
  - get_api_key: header ausente / formato malo / token incorrecto / token vacío.
  - require_auth: alias funcional.
  - get_api_key_user: alias backward-compatible.
  - Variable de entorno API_KEY: override y fallback default.

Política:
  - Sin secretos reales (TESTING_RULES.md §1).
  - Sin tocar lógica (solo Request mocks + monkeypatch env).
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.core.auth import get_api_key, get_api_key_user, require_auth


def _make_request(authorization: str | None) -> MagicMock:
    """Construye un Request-like con headers controlados."""
    req = MagicMock()
    req.headers = MagicMock()
    req.headers.get = MagicMock(
        side_effect=lambda k: authorization if k == "Authorization" else None
    )
    return req


# ─────────────────────────────────────────────────────────────────
# Header ausente / malformado → 401
# ─────────────────────────────────────────────────────────────────


def test_falta_header_authorization_devuelve_401():
    req = _make_request(None)
    with pytest.raises(HTTPException) as exc:
        get_api_key(req)
    assert exc.value.status_code == 401
    assert "Falta Authorization" in exc.value.detail


def test_authorization_sin_bearer_devuelve_401():
    req = _make_request("Token abc123")
    with pytest.raises(HTTPException) as exc:
        get_api_key(req)
    assert exc.value.status_code == 401
    assert "Formato Authorization inválido" in exc.value.detail


def test_authorization_basic_auth_devuelve_401():
    req = _make_request("Basic dXNlcjpwYXNz")
    with pytest.raises(HTTPException) as exc:
        get_api_key(req)
    assert exc.value.status_code == 401


def test_authorization_string_vacio_devuelve_401():
    """Cadena vacía es falsy → mismo path que header ausente."""
    req = _make_request("")
    with pytest.raises(HTTPException) as exc:
        get_api_key(req)
    assert exc.value.status_code == 401


# ─────────────────────────────────────────────────────────────────
# Token inválido vs válido
# ─────────────────────────────────────────────────────────────────


def test_token_incorrecto_devuelve_401(monkeypatch):
    monkeypatch.setenv("API_KEY", "real_key_xyz")
    req = _make_request("Bearer wrong_key")
    with pytest.raises(HTTPException) as exc:
        get_api_key(req)
    assert exc.value.status_code == 401
    assert "API key inválido" in exc.value.detail


def test_token_correcto_devuelve_token(monkeypatch):
    monkeypatch.setenv("API_KEY", "real_key_xyz")
    req = _make_request("Bearer real_key_xyz")
    assert get_api_key(req) == "real_key_xyz"


def test_token_correcto_con_espacios_extra_se_strippea(monkeypatch):
    """Token con whitespace adicional debe normalizarse antes de comparar."""
    monkeypatch.setenv("API_KEY", "real_key_xyz")
    req = _make_request("Bearer   real_key_xyz   ")
    assert get_api_key(req) == "real_key_xyz"


def test_sin_api_key_env_devuelve_500(monkeypatch):
    """Si API_KEY no está seteado, debe retornar 500 (servidor mal configurado)."""
    monkeypatch.delenv("API_KEY", raising=False)
    req = _make_request("Bearer cualquier_token")
    with pytest.raises(HTTPException) as exc:
        get_api_key(req)
    assert exc.value.status_code == 500
    assert "API_KEY" in exc.value.detail


def test_api_key_env_vacio_devuelve_500(monkeypatch):
    """API_KEY="" es falsy → 500 (servidor mal configurado)."""
    monkeypatch.setenv("API_KEY", "")
    req = _make_request("Bearer cualquier_token")
    with pytest.raises(HTTPException) as exc:
        get_api_key(req)
    assert exc.value.status_code == 500
    assert "API_KEY" in exc.value.detail


# ─────────────────────────────────────────────────────────────────
# require_auth (dependency)
# ─────────────────────────────────────────────────────────────────


def test_require_auth_pasa_token_through():
    """
    require_auth recibe el resultado de get_api_key vía Depends.
    Lo invocamos directo con un valor ya validado.
    """
    assert require_auth("token_validado") == "token_validado"


def test_get_api_key_user_es_alias_de_require_auth():
    """Backward-compat: get_api_key_user debe apuntar al mismo callable."""
    assert get_api_key_user is require_auth
