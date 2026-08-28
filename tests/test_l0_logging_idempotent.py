"""Ola 1/2 diagnóstico logs L0 — logging idempotente, banners una vez, rotación.

Paper-only. PROMOTE_LIVE: NO.
"""

from __future__ import annotations

import logging
from pathlib import Path

from app.core.boot_log import boot_info, reset_boot_log_for_tests
from app.core.optimized_logging import _build_logging_config
from app.core.sqlalchemy_logging import configure_sqlalchemy_logging


def test_worker_log_uses_rotating_file_handler(monkeypatch, tmp_path):
    monkeypatch.setenv("LOG_FILE_PATH", str(tmp_path / "gridbot.log"))
    monkeypatch.setenv("ENVIRONMENT", "development")
    cfg = _build_logging_config()
    file_h = cfg["handlers"]["file"]
    assert file_h["class"] == "logging.handlers.RotatingFileHandler"
    assert file_h["maxBytes"] == 10485760
    assert file_h["backupCount"] == 5
    assert Path(file_h["filename"]).name == "gridbot.log"


def test_setup_optimized_logging_idempotent(monkeypatch, tmp_path, capsys):
    from app.core import optimized_logging as ol

    monkeypatch.setenv("LOG_FILE_PATH", str(tmp_path / "gridbot.log"))
    monkeypatch.setenv("ENVIRONMENT", "development")
    ol._LOGGING_CONFIGURED = False
    ol.setup_optimized_logging()
    ol.setup_optimized_logging()
    out = capsys.readouterr().out
    assert out.count("Sistema de logging optimizado configurado") == 1
    assert ol._LOGGING_CONFIGURED is True
    ol._LOGGING_CONFIGURED = False


def test_boot_banners_info_once_per_process(caplog):
    reset_boot_log_for_tests()
    log = logging.getLogger("test.boot_log")
    with caplog.at_level(logging.DEBUG, logger="test.boot_log"):
        boot_info(log, "redis_cache", "🔄 Redis Cache inicializado")
        boot_info(log, "redis_cache", "🔄 Redis Cache inicializado")
        boot_info(log, "auto_circuit_breaker", "🛡️ Auto Circuit Breaker inicializado")
    infos = [r for r in caplog.records if r.levelno == logging.INFO]
    debugs = [r for r in caplog.records if r.levelno == logging.DEBUG]
    assert len(infos) == 2
    assert any("Redis Cache" in r.getMessage() for r in debugs)
    reset_boot_log_for_tests()


def test_sqlalchemy_logging_idempotent_no_print(capsys):
    configure_sqlalchemy_logging()
    configure_sqlalchemy_logging()
    captured = capsys.readouterr()
    assert "Configuración de SQLAlchemy" not in captured.out


def test_stamp_telegram_utc_skips_if_reloj_present():
    from app.services.telegram_alert import stamp_telegram_utc

    already = "hola\nReloj: 2026-08-28 12:00 UTC"
    assert stamp_telegram_utc(already) == already
    stamped = stamp_telegram_utc("alerta paper")
    assert stamped.startswith("alerta paper")
    assert "Reloj:" in stamped
    assert "UTC" in stamped
