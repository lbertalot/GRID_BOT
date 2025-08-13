import os
import sys
import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import settings
from app.services.binance_service import BinanceService


def test_settings_flags_from_env(monkeypatch):
    monkeypatch.setenv("PAPER_TRADING", "true")
    monkeypatch.setenv("BINANCE_TESTNET", "true")
    # Re-crear settings
    from importlib import reload
    import app.core.config as cfg
    reload(cfg)
    s = cfg.settings
    assert s.paper_trading is True
    assert s.binance_testnet is True


def test_binance_service_respects_paper_mode(monkeypatch):
    monkeypatch.setenv("PAPER_TRADING", "true")
    monkeypatch.setenv("BINANCE_TESTNET", "true")
    # Re-crear settings y servicio
    from importlib import reload
    import app.core.config as cfg
    reload(cfg)
    svc = BinanceService()
    assert svc.simulation_mode is True

