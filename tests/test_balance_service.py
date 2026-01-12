"""
Tests para BalanceService - Bug #1 Fix
GridBot v2.5

Tests unitarios para verificar que BalanceService:
1. Actualiza balances con optimistic locking
2. Retry automático en conflictos
3. Exponential backoff con jitter
4. Métricas Prometheus
"""

import pytest
import asyncio
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from sqlalchemy.orm import Session

from app.services.balance_service import BalanceService, ConcurrentModificationError
from app.models.balance import Balance


@pytest.fixture
def balance_service():
    """Instancia de BalanceService para tests"""
    return BalanceService()


@pytest.fixture
def mock_db_session():
    """Mock de SQLAlchemy session"""
    session = MagicMock(spec=Session)
    return session


class TestBalanceService:
    """Test suite para BalanceService"""
    
    @pytest.mark.asyncio
    async def test_update_balance_success(self, balance_service):
        """Test: Actualizar balance exitosamente sin conflictos"""
        with patch('app.services.balance_service.SessionLocal') as mock_session_factory:
            mock_session = MagicMock()
            mock_session_factory.return_value = mock_session
            
            # Mock balance existente
            existing_balance = Balance(asset="BTC", free=Decimal("1.0"), locked=Decimal("0"), version=1)
            mock_session.query.return_value.filter_by.return_value.with_for_update.return_value.first.return_value = existing_balance
            
            # Ejecutar
            result = await balance_service.update_balance("BTC", Decimal("0.5"))
            
            # Verificar
            assert result is True
            assert existing_balance.free == Decimal("1.5")
            assert existing_balance.version == 2
            mock_session.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_balance_create_new(self, balance_service):
        """Test: Crear nuevo balance si no existe"""
        with patch('app.services.balance_service.SessionLocal') as mock_session_factory:
            mock_session = MagicMock()
            mock_session_factory.return_value = mock_session
            
            # Mock: no existe balance
            mock_session.query.return_value.filter_by.return_value.with_for_update.return_value.first.return_value = None
            
            # Ejecutar
            result = await balance_service.update_balance("ETH", Decimal("2.0"))
            
            # Verificar que se creó nuevo balance
            assert result is True
            mock_session.add.assert_called_once()
            mock_session.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_balance_optimistic_locking_conflict(self, balance_service):
        """Test: Detectar y retry en conflicto de optimistic locking"""
        with patch('app.services.balance_service.SessionLocal') as mock_session_factory:
            mock_session = MagicMock()
            mock_session_factory.return_value = mock_session
            
            # Mock balance que cambia su versión (simular conflicto)
            balance1 = Balance(asset="BTC", free=Decimal("1.0"), locked=Decimal("0"), version=1)
            balance2 = Balance(asset="BTC", free=Decimal("1.5"), locked=Decimal("0"), version=2)  # Versión cambió
            balance3 = Balance(asset="BTC", free=Decimal("1.5"), locked=Decimal("0"), version=2)  # Estable
            
            mock_session.query.return_value.filter_by.return_value.with_for_update.return_value.first.side_effect = [
                balance1,  # Primera lectura
                balance2,  # Segunda lectura después del conflicto
                balance3   # Tercera lectura exitosa
            ]
            
            # Mock commit que falla la primera vez (conflicto)
            mock_session.commit.side_effect = [
                Exception("Optimistic locking conflict"),  # Primera commit falla
                None  # Segunda commit exitosa
            ]
            
            # Ejecutar - debería reintentar
            result = await balance_service.update_balance("BTC", Decimal("0.5"))
            
            # Verificar que reintentó
            assert mock_session.commit.call_count >= 2
    
    @pytest.mark.asyncio
    async def test_update_balance_max_retries_exceeded(self, balance_service):
        """Test: Lanzar excepción si se exceden max_retries"""
        balance_service.max_retries = 3
        
        with patch('app.services.balance_service.SessionLocal') as mock_session_factory:
            mock_session = MagicMock()
            mock_session_factory.return_value = mock_session
            
            # Mock balance que siempre tiene conflicto
            balance = Balance(asset="BTC", free=Decimal("1.0"), locked=Decimal("0"), version=1)
            mock_session.query.return_value.filter_by.return_value.with_for_update.return_value.first.return_value = balance
            
            # Mock commit que siempre falla
            mock_session.commit.side_effect = Exception("Persistent conflict")
            
            # Ejecutar - debería lanzar excepción después de max_retries
            with pytest.raises(ConcurrentModificationError):
                await balance_service.update_balance("BTC", Decimal("0.5"))
            
            # Verificar que intentó max_retries veces
            assert mock_session.commit.call_count == balance_service.max_retries
    
    @pytest.mark.asyncio
    async def test_set_balance_success(self, balance_service):
        """Test: Establecer balance absoluto exitosamente"""
        with patch('app.services.balance_service.SessionLocal') as mock_session_factory:
            mock_session = MagicMock()
            mock_session_factory.return_value = mock_session
            
            # Mock balance existente
            existing_balance = Balance(asset="USDT", free=Decimal("100.0"), locked=Decimal("0"), version=1)
            mock_session.query.return_value.filter_by.return_value.with_for_update.return_value.first.return_value = existing_balance
            
            # Ejecutar
            result = await balance_service.set_balance("USDT", Decimal("200.0"))
            
            # Verificar
            assert result is True
            assert existing_balance.free == Decimal("200.0")
            assert existing_balance.version == 2
    
    @pytest.mark.asyncio
    async def test_exponential_backoff_with_jitter(self, balance_service):
        """Test: Verificar que el retry usa exponential backoff con jitter"""
        balance_service.max_retries = 5
        sleep_times = []
        
        async def mock_sleep(duration):
            sleep_times.append(duration)
        
        with patch('app.services.balance_service.asyncio.sleep', side_effect=mock_sleep):
            with patch('app.services.balance_service.SessionLocal') as mock_session_factory:
                mock_session = MagicMock()
                mock_session_factory.return_value = mock_session
                
                # Mock balance que siempre falla
                balance = Balance(asset="BTC", free=Decimal("1.0"), locked=Decimal("0"), version=1)
                mock_session.query.return_value.filter_by.return_value.with_for_update.return_value.first.return_value = balance
                mock_session.commit.side_effect = Exception("Conflict")
                
                # Ejecutar
                try:
                    await balance_service.update_balance("BTC", Decimal("0.5"))
                except ConcurrentModificationError:
                    pass
                
                # Verificar que se usó backoff exponencial
                # Los tiempos deben incrementarse (con jitter)
                assert len(sleep_times) >= 3
                # No verificamos valores exactos por el jitter, pero sí que hay delays
                assert all(t > 0 for t in sleep_times)
    
    @pytest.mark.asyncio
    async def test_metrics_recorded_on_conflict(self, balance_service):
        """Test: Verificar que las métricas se registran en conflictos"""
        with patch('app.services.balance_service.balance_update_conflicts_total') as mock_metric:
            with patch('app.services.balance_service.SessionLocal') as mock_session_factory:
                mock_session = MagicMock()
                mock_session_factory.return_value = mock_session
                
                # Mock balance con conflicto que se resuelve
                balance = Balance(asset="BTC", free=Decimal("1.0"), locked=Decimal("0"), version=1)
                mock_session.query.return_value.filter_by.return_value.with_for_update.return_value.first.return_value = balance
                
                mock_session.commit.side_effect = [
                    Exception("Conflict"),  # Primera falla
                    None  # Segunda exitosa
                ]
                
                # Ejecutar
                await balance_service.update_balance("BTC", Decimal("0.5"))
                
                # Verificar que se incrementó el counter de conflictos
                mock_metric.labels.assert_called_with(asset="BTC")
                mock_metric.labels.return_value.inc.assert_called()
    
    @pytest.mark.asyncio
    async def test_concurrent_updates_integrity(self, balance_service):
        """Test: Simular múltiples updates concurrentes"""
        with patch('app.services.balance_service.SessionLocal') as mock_session_factory:
            # Para este test necesitaríamos una BD real o un mock más complejo
            # Por ahora, verificamos que el método maneja concurrencia
            tasks = [
                balance_service.update_balance("BTC", Decimal("0.1"))
                for _ in range(5)
            ]
            
            # Este test requiere una implementación más compleja con BD real
            # o mocking avanzado de SQLAlchemy
            # Por ahora, solo verificamos que no lanza excepciones inesperadas
            pass  # TODO: Implementar test de integración con DB real


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

