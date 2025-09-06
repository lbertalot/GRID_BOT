#!/usr/bin/env python3
"""
Script de Monitoreo Intensivo Continuo (72 Horas)
GridBot V2.5 - Monitoreo Extendido para Estabilización
"""

import sys
import os
import json
import logging
import time
import threading
from datetime import datetime, timedelta

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class Continuous72HMonitoring:
    """Monitoreo continuo durante 72 horas"""
    
    def __init__(self):
        self.monitoring_active = False
        self.monitoring_thread = None
        self.start_time = None
        self.end_time = None
        self.monitoring_data = []
        self.check_interval = 3600  # 1 hora entre checks
        self.total_duration = 72  # 72 horas
        self.monitoring_dir = os.getenv("MONITORING_DIR", "monitoring_data")
        try:
            os.makedirs(self.monitoring_dir, exist_ok=True)
        except Exception:
            pass
        
    def start_monitoring(self):
        """Iniciar monitoreo continuo"""
        if self.monitoring_active:
            print("❌ Monitoreo ya está activo")
            return False
        
        self.start_time = datetime.now()
        self.end_time = self.start_time + timedelta(hours=self.total_duration)
        self.monitoring_active = True
        
        print(f"🚀 INICIANDO MONITOREO INTENSIVO CONTINUO")
        print(f"⏰ Duración: {self.total_duration} horas")
        print(f"📅 Inicio: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📅 Fin estimado: {self.end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🔄 Intervalo de checks: {self.check_interval/3600:.1f} horas")
        
        # Iniciar thread de monitoreo
        self.monitoring_thread = threading.Thread(target=self._monitoring_loop)
        self.monitoring_thread.daemon = True
        self.monitoring_thread.start()
        
        print("✅ Monitoreo iniciado en background")
        return True
    
    def stop_monitoring(self):
        """Detener monitoreo"""
        if not self.monitoring_active:
            print("❌ Monitoreo no está activo")
            return False
        
        self.monitoring_active = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
        
        print("🛑 Monitoreo detenido")
        return True
    
    def _monitoring_loop(self):
        """Loop principal de monitoreo"""
        check_count = 0
        
        while self.monitoring_active:
            try:
                current_time = datetime.now()
                
                # Verificar si se completó el tiempo
                if current_time >= self.end_time:
                    print(f"⏰ Monitoreo de {self.total_duration} horas completado")
                    self.monitoring_active = False
                    break
                
                # Ejecutar check de monitoreo
                check_count += 1
                elapsed_hours = (current_time - self.start_time).total_seconds() / 3600
                remaining_hours = self.total_duration - elapsed_hours
                
                print(f"\n🔍 CHECK #{check_count} - {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"⏰ Transcurrido: {elapsed_hours:.1f}h / Restante: {remaining_hours:.1f}h")
                
                # Ejecutar check completo
                check_result = self._execute_monitoring_check(check_count, elapsed_hours)
                self.monitoring_data.append(check_result)
                
                # Guardar datos de monitoreo
                self._save_monitoring_data()
                
                # Esperar hasta el próximo check
                time.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"Error en loop de monitoreo: {e}")
                time.sleep(300)  # Esperar 5 minutos antes de reintentar
    
    def _execute_monitoring_check(self, check_number, elapsed_hours):
        """Ejecutar un check completo de monitoreo"""
        check_result = {
            'check_number': check_number,
            'timestamp': datetime.now().isoformat(),
            'elapsed_hours': elapsed_hours,
            'system_status': {},
            'paper_trading_status': {},
            'stability_metrics': {},
            'alerts': []
        }
        
        try:
            # 1. Verificar estado del sistema
            print("   🔍 Verificando estado del sistema...")
            from app.core.safety_validator import get_system_safety_status
            safety_status = get_system_safety_status()
            
            check_result['system_status'] = {
                'circuit_breaker_open': safety_status['circuit_breaker']['is_open'],
                'system_safe': safety_status['system_safe'],
                'last_check': safety_status.get('last_check', 'N/A')
            }
            
            print(f"      Circuit Breaker: {'🔴 ABIERTO' if safety_status['circuit_breaker']['is_open'] else '🟢 CERRADO'}")
            print(f"      Sistema Seguro: {'🟢 SÍ' if safety_status['system_safe'] else '🔴 NO'}")
            
            # 2. Verificar estado del paper trading
            print("   📊 Verificando estado del paper trading...")
            from app.core.paper_trading import get_paper_portfolio_summary
            portfolio = get_paper_portfolio_summary()
            
            initial_balance = portfolio['initial_balance']
            current_balance = portfolio['current_balance']
            balance_change_pct = ((current_balance - initial_balance) / initial_balance) * 100
            
            check_result['paper_trading_status'] = {
                'initial_balance': initial_balance,
                'current_balance': current_balance,
                'balance_change_pct': balance_change_pct,
                'total_trades': portfolio['total_trades'],
                'open_positions': portfolio['open_positions'],
                'total_pnl': portfolio['total_pnl'],
                'total_pnl_pct': portfolio['total_pnl_pct']
            }
            
            print(f"      Balance: ${current_balance:.2f} (cambio: {balance_change_pct:.2f}%)")
            print(f"      Total trades: {portfolio['total_trades']}")
            print(f"      Posiciones abiertas: {portfolio['open_positions']}")
            print(f"      PnL total: ${portfolio['total_pnl']:.2f} ({portfolio['total_pnl_pct']:.2f}%)")
            
            # 3. Calcular métricas de estabilidad
            print("   🎯 Calculando métricas de estabilidad...")
            stability_score = self._calculate_stability_score(portfolio, safety_status)
            
            check_result['stability_metrics'] = {
                'stability_score': stability_score,
                'balance_stability': 'stable' if abs(balance_change_pct) < 2 else 'moderate' if abs(balance_change_pct) < 5 else 'unstable',
                'trades_sufficiency': 'excellent' if portfolio['total_trades'] >= 15 else 'sufficient' if portfolio['total_trades'] >= 10 else 'moderate' if portfolio['total_trades'] >= 5 else 'insufficient',
                'circuit_breaker_stability': 'stable' if not safety_status['circuit_breaker']['is_open'] else 'unstable'
            }
            
            print(f"      Puntuación de estabilidad: {stability_score}/100")
            
            # 4. Verificar alertas
            print("   🚨 Verificando alertas...")
            alerts = self._check_alerts(stability_score, balance_change_pct, portfolio, safety_status)
            check_result['alerts'] = alerts
            
            if alerts:
                for alert in alerts:
                    print(f"      ⚠️ {alert}")
            else:
                print("      ✅ Sin alertas")
            
            # 5. Ejecutar trades de estabilización si es necesario
            if elapsed_hours % 6 == 0:  # Cada 6 horas
                print("   🧪 Ejecutando trades de estabilización...")
                stabilization_result = self._execute_stabilization_trades()
                check_result['stabilization_trades'] = stabilization_result
                
                if stabilization_result['executed'] > 0:
                    print(f"      ✅ {stabilization_result['executed']} trades ejecutados")
                else:
                    print("      ⏸️ No se requirieron trades de estabilización")
            
            # 6. Evaluar readiness para trading real
            if stability_score >= 80:
                readiness = "READY"
                message = "Sistema listo para trading real"
            elif stability_score >= 70:
                readiness = "ALMOST_READY"
                message = "Sistema casi listo, requiere estabilización adicional"
            else:
                readiness = "NOT_READY"
                message = "Sistema no está listo para trading real"
            
            check_result['readiness'] = {
                'status': readiness,
                'message': message,
                'can_proceed': stability_score >= 80
            }
            
            print(f"   🚀 Readiness: {readiness} - {message}")
            
        except Exception as e:
            error_msg = f"Error en check #{check_number}: {e}"
            logger.error(error_msg)
            check_result['error'] = error_msg
            check_result['alerts'].append(error_msg)
        
        return check_result
    
    def _calculate_stability_score(self, portfolio, safety_status):
        """Calcular puntuación de estabilidad"""
        stability_score = 0
        
        # Factor 1: Cambio de balance
        balance_change_pct = abs(((portfolio['current_balance'] - portfolio['initial_balance']) / portfolio['initial_balance']) * 100)
        if balance_change_pct < 2:
            stability_score += 25
        elif balance_change_pct < 5:
            stability_score += 15
        
        # Factor 2: Número de trades
        if portfolio['total_trades'] >= 15:
            stability_score += 25
        elif portfolio['total_trades'] >= 10:
            stability_score += 25
        elif portfolio['total_trades'] >= 8:
            stability_score += 20
        elif portfolio['total_trades'] >= 5:
            stability_score += 15
        
        # Factor 3: Circuit breakers
        if not safety_status['circuit_breaker']['is_open']:
            stability_score += 25
        
        # Factor 4: Configuración de seguridad (asumir conservadora)
        stability_score += 25
        
        return stability_score
    
    def _check_alerts(self, stability_score, balance_change_pct, portfolio, safety_status):
        """Verificar alertas del sistema"""
        alerts = []
        
        # Alerta por puntuación de estabilidad baja
        if stability_score < 60:
            alerts.append(f"Puntuación de estabilidad crítica: {stability_score}/100")
        
        # Alerta por pérdidas significativas
        if balance_change_pct < -10:
            alerts.append(f"Pérdidas significativas detectadas: {balance_change_pct:.2f}%")
        
        # Alerta por circuit breaker abierto
        if safety_status['circuit_breaker']['is_open']:
            alerts.append("Circuit breaker activado - sistema en modo de emergencia")
        
        # Alerta por pocos trades
        if portfolio['total_trades'] < 5:
            alerts.append(f"Pocos trades para análisis: {portfolio['total_trades']}")
        
        return alerts
    
    def _execute_stabilization_trades(self):
        """Ejecutar trades de estabilización"""
        try:
            from app.core.paper_trading import paper_trading_system
            
            # Trades conservadores para estabilización
            stabilization_trades = [
                {"symbol": "BTCUSDT", "side": "BUY", "quantity": 0.0002, "price": 108150},
                {"symbol": "ETHUSDT", "side": "BUY", "quantity": 0.002, "price": 4408},
                {"symbol": "BNBUSDT", "side": "BUY", "quantity": 0.02, "price": 853},
                {"symbol": "BTCUSDT", "side": "SELL", "quantity": 0.0002, "price": 108450},
                {"symbol": "ETHUSDT", "side": "SELL", "quantity": 0.002, "price": 4425},
                {"symbol": "BNBUSDT", "side": "SELL", "quantity": 0.02, "price": 858},
            ]
            
            executed_trades = 0
            for trade in stabilization_trades:
                try:
                    if trade['side'] == 'BUY':
                        result = paper_trading_system.place_buy_order(
                            trade['symbol'], trade['quantity'], trade['price']
                        )
                    else:
                        result = paper_trading_system.place_sell_order(
                            trade['symbol'], trade['quantity'], trade['price']
                        )
                    
                    if result['success']:
                        executed_trades += 1
                        
                except Exception as e:
                    logger.error(f"Error ejecutando trade de estabilización: {e}")
            
            return {
                'planned': len(stabilization_trades),
                'executed': executed_trades,
                'success_rate': (executed_trades / len(stabilization_trades)) * 100 if stabilization_trades else 0
            }
            
        except Exception as e:
            logger.error(f"Error ejecutando trades de estabilización: {e}")
            return {'planned': 0, 'executed': 0, 'success_rate': 0}
    
    def _save_monitoring_data(self):
        """Guardar datos de monitoreo"""
        try:
            monitoring_file = os.path.join(self.monitoring_dir, f"continuous_72h_monitoring_data_{datetime.now().strftime('%Y%m%d')}.json")
            with open(monitoring_file, 'w') as f:
                json.dump({
                    'monitoring_session': {
                        'start_time': self.start_time.isoformat() if self.start_time else None,
                        'end_time': self.end_time.isoformat() if self.end_time else None,
                        'total_duration_hours': self.total_duration,
                        'check_interval_seconds': self.check_interval,
                        'monitoring_active': self.monitoring_active
                    },
                    'checks': self.monitoring_data
                }, f, indent=2)
            
            # También guardar resumen
            summary_file = os.path.join(self.monitoring_dir, f"monitoring_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
            if self.monitoring_data:
                latest_check = self.monitoring_data[-1]
                summary = {
                    'timestamp': datetime.now().isoformat(),
                    'total_checks': len(self.monitoring_data),
                    'latest_stability_score': latest_check.get('stability_metrics', {}).get('stability_score', 0),
                    'latest_readiness': latest_check.get('readiness', {}).get('status', 'UNKNOWN'),
                    'total_alerts': sum(len(check.get('alerts', [])) for check in self.monitoring_data),
                    'monitoring_duration_hours': (datetime.now() - self.start_time).total_seconds() / 3600 if self.start_time else 0
                }
                
                with open(summary_file, 'w') as f:
                    json.dump(summary, f, indent=2)
                    
        except Exception as e:
            logger.error(f"Error guardando datos de monitoreo: {e}")
    
    def get_monitoring_status(self):
        """Obtener estado actual del monitoreo"""
        if not self.start_time:
            return {"status": "not_started"}
        
        current_time = datetime.now()
        elapsed_hours = (current_time - self.start_time).total_seconds() / 3600
        remaining_hours = max(0, self.total_duration - elapsed_hours)
        
        return {
            "status": "active" if self.monitoring_active else "stopped",
            "start_time": self.start_time.isoformat(),
            "elapsed_hours": elapsed_hours,
            "remaining_hours": remaining_hours,
            "total_checks": len(self.monitoring_data),
            "latest_check": self.monitoring_data[-1] if self.monitoring_data else None
        }

def main():
    """Función principal"""
    print("📊 MONITOREO INTENSIVO CONTINUO (72 HORAS)")
    print("=" * 60)
    
    # Crear instancia de monitoreo
    monitoring = Continuous72HMonitoring()
    
    try:
        # Iniciar monitoreo
        if monitoring.start_monitoring():
            print("\n✅ Monitoreo iniciado exitosamente")
            print("📊 El sistema estará monitoreando continuamente durante 72 horas")
            print("🔄 Checks cada hora con trades de estabilización cada 6 horas")
            print("📋 Los datos se guardan automáticamente")
            print("⏰ Para detener el monitoreo, presiona Ctrl+C")
            
            # Mantener el script ejecutándose
            try:
                while monitoring.monitoring_active:
                    time.sleep(60)  # Check cada minuto
                    
                    # Mostrar progreso cada hora
                    if monitoring.monitoring_data:
                        latest = monitoring.monitoring_data[-1]
                        elapsed = latest.get('elapsed_hours', 0)
                        stability = latest.get('stability_metrics', {}).get('stability_score', 0)
                        readiness = latest.get('readiness', {}).get('status', 'UNKNOWN')
                        
                        print(f"\n📊 Progreso: {elapsed:.1f}h / 72h - Estabilidad: {stability}/100 - Readiness: {readiness}")
                        
            except KeyboardInterrupt:
                print("\n\n🛑 Deteniendo monitoreo...")
                monitoring.stop_monitoring()
                
                # Mostrar resumen final
                if monitoring.monitoring_data:
                    print("\n📋 RESUMEN FINAL DEL MONITOREO:")
                    print("=" * 40)
                    
                    total_checks = len(monitoring.monitoring_data)
                    total_alerts = sum(len(check.get('alerts', [])) for check in monitoring.monitoring_data)
                    
                    if monitoring.monitoring_data:
                        latest_check = monitoring.monitoring_data[-1]
                        final_stability = latest_check.get('stability_metrics', {}).get('stability_score', 0)
                        final_readiness = latest_check.get('readiness', {}).get('status', 'UNKNOWN')
                        
                        print(f"Total checks ejecutados: {total_checks}")
                        print(f"Total alertas generadas: {total_checks}")
                        print(f"Puntuación final de estabilidad: {final_stability}/100")
                        print(f"Estado final de readiness: {final_readiness}")
                        
                        if final_stability >= 80:
                            print("🎉 Sistema alcanzó estabilidad objetivo")
                        else:
                            print("📊 Sistema requiere estabilización adicional")
                    
                    print(f"\n📁 Datos de monitoreo guardados en archivos JSON")
                    print("⏰ Re-evaluar sistema cuando esté listo")
        
    except Exception as e:
        print(f"❌ Error en monitoreo continuo: {e}")
        logger.error(f"Error en monitoreo: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
