"""
Modelo PortfolioSnapshot — registra el valor total del portafolio cada 15 minutos.
Usado por performance_analyzer.py para calcular métricas reales (retorno, volatilidad,
drawdown) en lugar de datos simulados.
"""
from sqlalchemy import Column, Integer, Float, DateTime, String, Index
from sqlalchemy.sql import func
from app.models.base import Base


class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    # Valor total del portafolio convertido a USDT
    total_value_usdt = Column(Float, nullable=False)
    # Desglose por componente (USDT libre, BTC, resto de activos)
    usdt_free = Column(Float, nullable=False, default=0.0)
    btc_value_usdt = Column(Float, nullable=False, default=0.0)
    other_assets_usdt = Column(Float, nullable=False, default=0.0)
    # Precio de referencia BTC/USDT en el momento del snapshot
    btc_price = Column(Float, nullable=True)
    # Símbolo principal que el bot está operando
    primary_symbol = Column(String(20), nullable=True)
    # Marca de tiempo UTC del snapshot
    captured_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    def __repr__(self) -> str:
        return (
            f"<PortfolioSnapshot(id={self.id}, "
            f"total={self.total_value_usdt:.2f} USDT, "
            f"at={self.captured_at})>"
        )


# Índice compuesto para queries de rango temporal frecuentes
Index("ix_portfolio_snapshots_captured_at_desc", PortfolioSnapshot.captured_at)
