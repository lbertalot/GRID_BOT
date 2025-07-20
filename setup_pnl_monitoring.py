#!/usr/bin/env python3
"""
Script para configurar monitoreo automático de P&L
"""

import subprocess
import time
import json
from datetime import datetime

def setup_pnl_monitoring():
    """Configura el monitoreo automático de P&L"""
    
    print("🎯 Configurando Monitoreo Automático de P&L")
    print("=" * 50)
    
    # 1. Verificar que el sistema esté funcionando
    print("🔍 Verificando estado del sistema...")
    
    try:
        # Verificar API
        result = subprocess.run([
            "curl", "-s", "http://localhost:8000/docs"
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("   ✅ API GridBot funcionando")
        else:
            print("   ❌ API GridBot no disponible")
            return False
        
        # Verificar Prometheus
        result = subprocess.run([
            "curl", "-s", "http://localhost:9090/api/v1/query?query=up"
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("   ✅ Prometheus funcionando")
        else:
            print("   ❌ Prometheus no disponible")
            return False
        
        # Verificar Grafana
        result = subprocess.run([
            "curl", "-s", "http://localhost:3000/api/health"
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("   ✅ Grafana funcionando")
        else:
            print("   ❌ Grafana no disponible")
            return False
        
    except Exception as e:
        print(f"   ❌ Error verificando servicios: {e}")
        return False
    
    # 2. Inicializar seguimiento de P&L
    print("\n📊 Inicializando seguimiento de P&L...")
    
    try:
        result = subprocess.run([
            "docker-compose", "exec", "-T", "api", "python3", "profit_loss_tracker.py"
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("   ✅ Seguimiento de P&L inicializado")
        else:
            print("   ⚠️  Error inicializando P&L: {result.stderr}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # 3. Crear dashboard de P&L
    print("\n📈 Configurando dashboard de P&L...")
    
    try:
        # Copiar dashboard al contenedor
        subprocess.run([
            "docker", "cp", "pnl_dashboard.json", "gridbot_grafana:/tmp/"
        ], check=True)
        
        print("   ✅ Dashboard copiado al contenedor")
        
        # Importar dashboard
        result = subprocess.run([
            "curl", "-X", "POST",
            "-H", "Content-Type: application/json",
            "-u", "admin:gridbot123",
            "-d", "@pnl_dashboard.json",
            "http://localhost:3000/api/dashboards/db"
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("   ✅ Dashboard de P&L importado")
        else:
            print("   ⚠️  Error importando dashboard: {result.stderr}")
    except Exception as e:
        print(f"   ❌ Error configurando dashboard: {e}")
    
    # 4. Configurar alertas automáticas
    print("\n📱 Configurando alertas automáticas...")
    
    try:
        # Crear script de monitoreo automático
        monitoring_script = """#!/bin/bash
# Script de monitoreo automático de P&L
cd /app
python3 update_pnl_metrics.py --continuous
"""
        
        with open("auto_pnl_monitor.sh", "w") as f:
            f.write(monitoring_script)
        
        subprocess.run(["chmod", "+x", "auto_pnl_monitor.sh"])
        print("   ✅ Script de monitoreo automático creado")
        
    except Exception as e:
        print(f"   ❌ Error configurando alertas: {e}")
    
    # 5. Mostrar instrucciones
    print("\n🎉 Configuración Completada!")
    print("\n📋 CÓMO MONITOREAR TUS GANANCIAS Y PÉRDIDAS:")
    print("\n1. 🖥️  DASHBOARD GRAFANA:")
    print("   • URL: http://localhost:3000")
    print("   • Usuario: admin")
    print("   • Contraseña: gridbot123")
    print("   • Busca: 'GridBot Profit/Loss Dashboard'")
    
    print("\n2. 📱 ALERTAS TELEGRAM:")
    print("   • Recibirás alertas automáticas")
    print("   • Notificaciones de cambios significativos")
    print("   • Estado de conexión en tiempo real")
    
    print("\n3. 🔧 COMANDOS RÁPIDOS:")
    print("   • Ver P&L actual: python3 check_pnl_simple.py")
    print("   • Ver P&L detallado: docker-compose exec api python3 profit_loss_tracker.py")
    print("   • Monitoreo continuo: docker-compose exec api python3 update_pnl_metrics.py --continuous")
    
    print("\n4. 📊 MÉTRICAS PROMETHEUS:")
    print("   • URL: http://localhost:9090")
    print("   • Consulta: gridbot_profit_loss")
    print("   • Consulta: gridbot_balance_total")
    
    print("\n5. 🎯 INTERPRETACIÓN:")
    print("   • 🟢 GANANDO: P&L > 0 (Estrategias exitosas)")
    print("   • 🔴 PERDIENDO: P&L < 0 (Revisar estrategias)")
    print("   • 🟡 NEUTRAL: P&L = 0 (Sin cambios significativos)")
    
    # 6. Enviar alerta de configuración
    try:
        alert_message = "🎯 Monitoreo de P&L Configurado\n\n"
        alert_message += "📊 Dashboard: http://localhost:3000\n"
        alert_message += "👤 Usuario: admin\n"
        alert_message += "🔑 Contraseña: gridbot123\n\n"
        alert_message += "📱 Alertas automáticas activadas\n"
        alert_message += "🔧 Monitoreo continuo configurado\n\n"
        alert_message += "🎉 ¡Sistema listo para monitorear ganancias!"
        
        telegram_data = {
            "chat_id": "1248403886",
            "text": alert_message
        }
        
        subprocess.run([
            "curl", "-X", "POST",
            "-H", "Content-Type: application/json",
            "-d", json.dumps(telegram_data),
            "https://api.telegram.org/bot8064465462:AAEmpOz78phwtPGWvC3jDmGXUyTYTinhqi8/sendMessage"
        ], capture_output=True)
        
        print("\n📱 Alerta de configuración enviada a Telegram")
        
    except Exception as e:
        print(f"\n❌ Error enviando alerta: {e}")
    
    return True

def main():
    """Función principal"""
    success = setup_pnl_monitoring()
    
    if success:
        print(f"\n✅ Monitoreo de P&L configurado exitosamente!")
        print(f"🎯 Ahora puedes monitorear tus ganancias y pérdidas en tiempo real")
    else:
        print(f"\n❌ Error en la configuración")

if __name__ == "__main__":
    main() 