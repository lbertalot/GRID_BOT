import os
import sys
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Asegurar que el path del proyecto esté en PYTHONPATH para resolver 'app/*'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.models.base import Base
from app.models.performance_metrics import PerformanceMetrics
from app.models.alerts import Alert
from app.models.system_config import SystemConfig


@pytest.fixture
def in_memory_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


def test_system_config_crud(in_memory_db):
    session = in_memory_db
    cfg = SystemConfig(key="trading_enabled", value="true", description="Feature flag")
    session.add(cfg)
    session.commit()
    fetched = session.query(SystemConfig).filter_by(key="trading_enabled").first()
    assert fetched is not None
    assert fetched.value == "true"


def test_alerts_insert(in_memory_db):
    session = in_memory_db
    alert = Alert(type="SYSTEM", message="Bot started")
    session.add(alert)
    session.commit()
    assert session.query(Alert).count() == 1


def test_performance_metrics_defaults(in_memory_db):
    session = in_memory_db
    pm = PerformanceMetrics()
    session.add(pm)
    session.commit()
    stored = session.query(PerformanceMetrics).first()
    assert stored.total_trades == 0
    assert stored.total_profit == 0.0


