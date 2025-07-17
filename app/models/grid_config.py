from sqlalchemy import Column, Integer, String, Float
from app.models.base import Base

class GridConfig(Base):
    __tablename__ = "grid_config"
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, default="BTCUSDT")
    min_price = Column(Float, default=20000)
    max_price = Column(Float, default=30000)
    grids = Column(Integer, default=5)
    quantity = Column(Float, default=0.001)
    last_action = Column(String, nullable=True) 