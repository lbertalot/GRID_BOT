from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text

from app.models.base import Base


class SystemSetting(Base):
    __tablename__ = "system_settings"

    key = Column(String(128), primary_key=True, nullable=False)
    value = Column(Text, nullable=True)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
