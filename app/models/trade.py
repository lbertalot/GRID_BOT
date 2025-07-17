from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy.sql import func
from app.models.base import Base

class Trade(Base):
    __tablename__ = "trades"
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True)
    side = Column(String)  # BUY o SELL
    quantity = Column(Float)
    entry_price = Column(Float)
    exit_price = Column(Float, nullable=True)
    profit_loss = Column(Float, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now()) 