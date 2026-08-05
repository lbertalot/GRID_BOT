"""
S11 / B24 — Tests de redacción de secrets en logs.

Garantiza que ningún prefijo/substring (≥4 chars) de api_key / api_secret
aparezca en salida de logging. Regresión estática contra `secret[:N]` en app/.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.core.secret_redaction import (
    assert_no_secret_leak,
    format_credential_for_log,
    redact_secret,
    secret_fingerprint,
)

# Key de prueba conocida (no es un secreto real). Suficientemente larga para
# capturar leaks de prefijos [:6]/[:10] y substrings ≥4.
# Solo letras g–z (fuera del alfabeto hex) para que un fingerprint SHA no
# genere falsos positivos en assert_no_secret_leak.
KNOWN_API_KEY = "GhIjKlMnOpQrStUvWxYzGhIjKlMnOpQrStUv"
KNOWN_SECRET_KEY = "PoNmLkJiHgZyXwVuTsRqPoNmLkJiHgZyXwVu"


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_DIR = REPO_ROOT / "app"

# Patrones que indican filtración parcial de secrets en código fuente.
_LEAK_SLICE_RE = re.compile(
    r"""(?x)
    (?:api_key|api_secret|secret_key|password|token|apiKey|secretKey)
    \s*
    (?:\)\s*)?          # opcional cierre de getattr/attr
    \[
    \s*:\s*\d+\s*
    \]
    |
    (?:client|self(?:\._client)?)\.api_key\s*\[\s*:\s*\d+\s*\]
    """,
)


class _ListHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)

    @property
    def text(self) -> str:
        return "\n".join(r.getMessage() for r in self.records)


def _attach_capture(logger_name: str) -> tuple[logging.Logger, _ListHandler]:
    handler = _ListHandler()
    logger = logging.getLogger(logger_name)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    # Evitar que el root duplique y ensucie otras capturas.
    logger.propagate = False
    return logger, handler


def test_redact_secret_nunca_incluye_material():
    out = redact_secret(KNOWN_API_KEY, label="api_key")
    assert out == "api_key=***"
    assert_no_secret_leak(out, KNOWN_API_KEY)


def test_format_credential_fingerprint_estable_y_sin_leak():
    a = format_credential_for_log(KNOWN_API_KEY, label="api_key")
    b = format_credential_for_log(KNOWN_API_KEY, label="api_key")
    assert a == b
    assert a.startswith("api_key=*** fp=")
    assert_no_secret_leak(a, KNOWN_API_KEY)
    fp = secret_fingerprint(KNOWN_API_KEY)
    assert fp in a
    # Fingerprint distinto para otro secret
    assert secret_fingerprint(KNOWN_SECRET_KEY) != fp


def test_assert_no_secret_leak_detecta_prefijo():
    with pytest.raises(AssertionError, match="Secret leak"):
        assert_no_secret_leak(f"key={KNOWN_API_KEY[:10]}...", KNOWN_API_KEY)


def test_get_binance_credentials_no_loguea_prefijos(monkeypatch):
    monkeypatch.setenv("BINANCE_API_KEY", KNOWN_API_KEY)
    monkeypatch.setenv("BINANCE_SECRET_KEY", KNOWN_SECRET_KEY)
    monkeypatch.setenv("DEBUG", "false")

    _, handler = _attach_capture("app.services.binance_credentials")

    from app.services import binance_credentials as creds

    api_key, secret_key = creds.get_binance_credentials()
    assert api_key == KNOWN_API_KEY
    assert secret_key == KNOWN_SECRET_KEY

    assert_no_secret_leak(handler.text, KNOWN_API_KEY)
    assert_no_secret_leak(handler.text, KNOWN_SECRET_KEY)
    assert "api_key=***" in handler.text or "API_KEY" in handler.text.upper()


def test_get_binance_credentials_debug_tampoco_loguea_prefijos(monkeypatch):
    monkeypatch.setenv("BINANCE_API_KEY", KNOWN_API_KEY)
    monkeypatch.setenv("BINANCE_SECRET_KEY", KNOWN_SECRET_KEY)
    monkeypatch.setenv("DEBUG", "true")

    _, handler = _attach_capture("app.services.binance_credentials")

    from app.services import binance_credentials as creds

    creds.get_binance_credentials()
    assert_no_secret_leak(handler.text, KNOWN_API_KEY)
    assert_no_secret_leak(handler.text, KNOWN_SECRET_KEY)


def test_create_binance_client_no_loguea_prefijos(monkeypatch):
    _, handler = _attach_capture("app.services.binance_credentials")

    fake = MagicMock()
    fake.api_key = KNOWN_API_KEY
    fake.api_secret = KNOWN_SECRET_KEY

    with patch("app.services.binance_credentials.Client", return_value=fake):
        from app.services import binance_credentials as creds

        client = creds.create_binance_client(KNOWN_API_KEY, KNOWN_SECRET_KEY, testnet=False)

    assert client is fake
    assert_no_secret_leak(handler.text, KNOWN_API_KEY)
    assert_no_secret_leak(handler.text, KNOWN_SECRET_KEY)


def test_singleton_init_no_loguea_prefijos(monkeypatch):
    monkeypatch.setenv("BINANCE_API_KEY", KNOWN_API_KEY)
    monkeypatch.setenv("BINANCE_SECRET_KEY", KNOWN_SECRET_KEY)
    monkeypatch.setenv("BINANCE_TESTNET", "false")

    _, handler = _attach_capture("app.services.binance_client_singleton")

    fake = MagicMock()
    fake.api_key = KNOWN_API_KEY
    fake.api_secret = KNOWN_SECRET_KEY
    fake.get_account.return_value = {"balances": []}

    with (
        patch("app.services.binance_client_singleton.Client", return_value=fake),
        patch("app.services.binance_client_singleton.get_binance_proxies", return_value=None),
        patch("app.core.binance_proxy.log_proxy_status"),
    ):
        from app.services.binance_client_singleton import BinanceClientSingleton

        # Forzar re-init aislado
        singleton = BinanceClientSingleton.__new__(BinanceClientSingleton)
        singleton._client = None
        singleton._initialized = False
        singleton._initialize_client()

    assert_no_secret_leak(handler.text, KNOWN_API_KEY)
    assert_no_secret_leak(handler.text, KNOWN_SECRET_KEY)


def test_source_app_no_slice_de_secrets():
    """Regresión estática: ningún `api_key[:N]` (ni variantes) en app/."""
    offenders: list[str] = []
    for path in APP_DIR.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for i, line in enumerate(text.splitlines(), start=1):
            if line.lstrip().startswith("#"):
                continue
            if _LEAK_SLICE_RE.search(line):
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{i}: {line.strip()}")

    assert not offenders, (
        "Filtración parcial de secrets en código fuente:\n" + "\n".join(offenders)
    )
