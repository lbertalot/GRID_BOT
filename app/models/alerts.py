from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.sql import func
from app.models.base import Base


class Alert(Base):
    """
    Alertas del sistema (profit, loss, system, error) con estado de envío.
    """
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True)
    type = Column(String(50), nullable=False)
    message = Column(Text, nullable=False)
    level = Column(String(20), default="INFO")
    sent_to_telegram = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


