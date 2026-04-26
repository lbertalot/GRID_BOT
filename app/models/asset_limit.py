from sqlalchemy import Column, String, Float, DateTime
from sqlalchemy.sql import func
from app.models.base import Base


class AssetLimit(Base):
    """
    Modelo para almacenar los límites de trading de un activo de Binance.
    """

    __tablename__ = "asset_limits"

    symbol = Column(String, primary_key=True)
    min_price = Column(Float, nullable=False)
    max_price = Column(Float, nullable=False)
    tick_size = Column(Float, nullable=False)  # Price filter
    min_qty = Column(Float, nullable=False)
    max_qty = Column(Float, nullable=False)
    step_size = Column(Float, nullable=False)  # Lot size filter
    min_notional = Column(Float, nullable=False)  # Min notional filter
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self):
        return (
            f"<AssetLimit(symbol='{self.symbol}', min_price={self.min_price}, max_price={self.max_price}, "
            f"tick_size={self.tick_size}, min_qty={self.min_qty}, max_qty={self.max_qty}, "
            f"step_size={self.step_size}, min_notional={self.min_notional})>"
        )
