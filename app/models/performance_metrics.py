from sqlalchemy import Column, Integer, Float, DateTime
from sqlalchemy.sql import func
from app.models.base import Base


class PerformanceMetrics(Base):
    """
    Métricas agregadas del sistema de trading.
    """
    __tablename__ = "performance_metrics"

    id = Column(Integer, primary_key=True)
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    total_profit = Column(Float, default=0.0)
    total_loss = Column(Float, default=0.0)
    win_rate = Column(Float, default=0.0)
    sharpe_ratio = Column(Float, default=0.0)
    max_drawdown = Column(Float, default=0.0)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())


