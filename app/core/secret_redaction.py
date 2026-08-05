"""Redacción segura de secrets para logs (B24 / S11).

Nunca loguear prefijos ni substrings de api_key / api_secret / tokens.
Para correlación usar fingerprint SHA-256 truncado (no reversible).
"""

from __future__ import annotations

import hashlib
from typing import Optional

_MIN_LEAK_SUBSTRING = 4


def secret_fingerprint(value: Optional[str], *, length: int = 8) -> str:
    """Fingerprint corto no reversible (SHA-256 hex truncado)."""
    if not value:
        return "none"
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return digest[: max(1, length)]


def redact_secret(value: Optional[str] = None, *, label: str = "secret") -> str:
    """Label seguro para logs. Nunca incluye material del secreto."""
    if not value:
        return f"{label}=<missing>"
    return f"{label}=***"


def format_credential_for_log(
    value: Optional[str],
    *,
    label: str = "api_key",
) -> str:
    """Redacción + fingerprint para correlacionar sin filtrar el secreto."""
    if not value:
        return f"{label}=<missing>"
    return f"{label}=*** fp={secret_fingerprint(value)}"


def assert_no_secret_leak(log_text: str, secret: str, *, min_len: int = _MIN_LEAK_SUBSTRING) -> None:
    """Falla si ``log_text`` contiene algún substring de ``secret`` de longitud ≥ min_len."""
    if not secret or len(secret) < min_len:
        return
    lowered = log_text.lower()
    secret_l = secret.lower()
    for i in range(0, len(secret_l) - min_len + 1):
        chunk = secret_l[i : i + min_len]
        if chunk in lowered:
            raise AssertionError(
                f"Secret leak: substring of length {min_len}+ found in log output"
            )
