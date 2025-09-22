"""
Circuit Breakers - Módulo de Circuit Breakers Simplificado
GridBot v2.5 - Componente de Integridad Integrado
"""

import logging
import time
from typing import Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class CircuitBreakers:
    """Clase simplificada de circuit breakers para componentes de integridad"""
    
    def __init__(self):
        self.logger = logger
        self.breakers = {
            'balance_discrepancy': {'active': False, 'activated_at': None, 'reason': None},
            'operation_failure_rate': {'active': False, 'activated_at': None, 'reason': None},
            'system_integrity': {'active': False, 'activated_at': None, 'reason': None},
            'critical_mode': {'active': False, 'activated_at': None, 'reason': None}
        }
        self.logger.info("🔧 Módulo de circuit breakers inicializado")
        # Cooldown por breaker y estado
        self._last_activation_ts: Dict[str, float] = {}
        import os
        try:
            self._cooldown_seconds = int(os.getenv("CB_COOLDOWN_SECONDS", "300"))
        except Exception:
            self._cooldown_seconds = 300  # 5 minutos
    
    async def activate_breaker(self, breaker_type: str, reason: str = None) -> bool:
        """Activar un circuit breaker específico"""
        try:
            if breaker_type not in self.breakers:
                self.logger.warning(f"⚠️ Tipo de circuit breaker desconocido: {breaker_type}")
                return False
            
            # Edge-trigger: solo loggear/cambiar estado si pasa de inactivo a activo
            if not self.breakers[breaker_type]['active']:
                # Cooldown: evitar flapping
                now = time.time()
                last = self._last_activation_ts.get(breaker_type, 0.0)
                if now - last < self._cooldown_seconds:
                    self.logger.warning(f"⏳ Cooldown activo para '{breaker_type}', activación omitida")
                    return False
                self.breakers[breaker_type]['active'] = True
                self.breakers[breaker_type]['activated_at'] = datetime.now().isoformat()
                self.breakers[breaker_type]['reason'] = reason or f"Activado automáticamente"
                self._last_activation_ts[breaker_type] = now
                self.logger.warning(f"🚨 Circuit breaker '{breaker_type}' activado: {reason}")
                # Métrica de estado
                try:
                    from app.core.metrics import breaker_state
                    breaker_state.labels(type=breaker_type).set(1)
                except Exception:
                    pass
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error activando circuit breaker '{breaker_type}': {e}")
            return False
    
    async def deactivate_breaker(self, breaker_type: str) -> bool:
        """Desactivar un circuit breaker específico"""
        try:
            if breaker_type not in self.breakers:
                self.logger.warning(f"⚠️ Tipo de circuit breaker desconocido: {breaker_type}")
                return False
            
            self.breakers[breaker_type]['active'] = False
            self.breakers[breaker_type]['activated_at'] = None
            self.breakers[breaker_type]['reason'] = None
            
            self.logger.info(f"✅ Circuit breaker '{breaker_type}' desactivado")
            try:
                from app.core.metrics import breaker_state
                breaker_state.labels(type=breaker_type).set(0)
            except Exception:
                pass
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error desactivando circuit breaker '{breaker_type}': {e}")
            return False
    
    async def activate_critical_mode(self) -> bool:
        """Activar modo crítico (todos los circuit breakers)"""
        try:
            for breaker_type in self.breakers:
                await self.activate_breaker(breaker_type, "Modo crítico activado")
            
            # Activar modo crítico especial
            self.breakers['critical_mode']['active'] = True
            self.breakers['critical_mode']['activated_at'] = datetime.now().isoformat()
            self.breakers['critical_mode']['reason'] = "MODO CRÍTICO - TODOS LOS CIRCUIT BREAKERS ACTIVADOS"
            
            self.logger.critical("🚨🚨🚨 MODO CRÍTICO ACTIVADO - TODOS LOS CIRCUIT BREAKERS ACTIVADOS 🚨🚨🚨")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error activando modo crítico: {e}")
            return False
    
    async def deactivate_critical_mode(self) -> bool:
        """Desactivar modo crítico"""
        try:
            for breaker_type in self.breakers:
                await self.deactivate_breaker(breaker_type)
            
            self.logger.info("✅ Modo crítico desactivado - todos los circuit breakers desactivados")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error desactivando modo crítico: {e}")
            return False
    
    def is_breaker_active(self, breaker_type: str) -> bool:
        """Verificar si un circuit breaker está activo"""
        if breaker_type not in self.breakers:
            return False
        return self.breakers[breaker_type]['active']
    
    def is_critical_mode_active(self) -> bool:
        """Verificar si el modo crítico está activo"""
        return self.breakers['critical_mode']['active']
    
    def is_trading_halted(self) -> bool:
        """Verificar si el trading está detenido por circuit breakers"""
        # Trading está detenido si hay cualquier circuit breaker activo
        return any(status['active'] for status in self.breakers.values())
    
    def get_breaker_status(self, breaker_type: str) -> Dict[str, Any]:
        """Obtener estado de un circuit breaker específico"""
        if breaker_type not in self.breakers:
            return {'error': f"Tipo de circuit breaker desconocido: {breaker_type}"}
        
        return self.breakers[breaker_type].copy()
    
    def get_all_breakers_status(self) -> Dict[str, Any]:
        """Obtener estado de todos los circuit breakers"""
        return {
            'critical_mode': self.is_critical_mode_active(),
            'active_breakers': [name for name, status in self.breakers.items() if status['active']],
            'total_active': sum(1 for status in self.breakers.values() if status['active']),
            'breakers': self.breakers.copy()
        }
    
    def get_breaker_summary(self) -> str:
        """Obtener resumen de circuit breakers en formato texto"""
        active_count = sum(1 for status in self.breakers.values() if status['active'])
        total_count = len(self.breakers)
        
        summary = f"📊 CIRCUIT BREAKERS: {active_count}/{total_count} activos\n\n"
        
        for name, status in self.breakers.items():
            emoji = "🔴" if status['active'] else "🟢"
            status_text = "ACTIVO" if status['active'] else "INACTIVO"
            summary += f"{emoji} {name}: {status_text}\n"
            
            if status['active'] and status['reason']:
                summary += f"   Razón: {status['reason']}\n"
                summary += f"   Activado: {status['activated_at']}\n"
            summary += "\n"
        
        return summary
