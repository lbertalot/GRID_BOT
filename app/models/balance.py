"""
Modelo Balance para optimistic locking
"""

from sqlalchemy import Column, Integer, String, Numeric, DateTime
from app.models.base import Base
from datetime import datetime


class Balance(Base):
    """Modelo de Balance con optimistic locking"""

    __tablename__ = "balances"

    id = Column(Integer, primary_key=True, index=True)
    asset = Column(String(20), unique=True, nullable=False, index=True)
    amount = Column(Numeric(20, 8), nullable=False, default=0)
    version = Column(Integer, default=0, nullable=False)  # Para optimistic locking
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Balance(asset={self.asset}, amount={self.amount}, version={self.version})>"
