import os
import importlib


def test_settings_production_requires_secret_key(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.delenv("SECRET_KEY", raising=False)
    # Forzar recarga del módulo config
    import app.core.config as cfg
    importlib.reload(cfg)
    try:
        _ = cfg.Settings()
        assert False, "Se esperaba ValueError por SECRET_KEY ausente en producción"
    except ValueError as e:
        assert "SECRET_KEY" in str(e)


def test_settings_debug_false_in_production(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "x")
    monkeypatch.setenv("DEBUG", "true")
    import app.core.config as cfg
    importlib.reload(cfg)
    try:
        _ = cfg.Settings()
        assert False, "Se esperaba ValueError por DEBUG=true en producción"
    except ValueError as e:
        assert "DEBUG" in str(e)


