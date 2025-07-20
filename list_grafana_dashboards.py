#!/usr/bin/env python3
"""
Script para listar todos los dashboards disponibles en Grafana
"""

import subprocess
import json

def list_grafana_dashboards():
    """Lista todos los dashboards disponibles en Grafana"""
    
    print("📊 Dashboards Disponibles en Grafana")
    print("=" * 50)
    
    try:
        # Obtener lista de dashboards
        result = subprocess.run([
            "curl", "-s", "-u", "admin:gridbot123",
            "http://localhost:3000/api/search"
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            dashboards = json.loads(result.stdout)
            
            if dashboards:
                print("🎯 Dashboards encontrados:")
                print()
                
                for i, dashboard in enumerate(dashboards, 1):
                    title = dashboard.get('title', 'Sin título')
                    uid = dashboard.get('uid', 'Sin UID')
                    url = dashboard.get('url', '')
                    
                    print(f"{i}. 📈 {title}")
                    print(f"   🆔 UID: {uid}")
                    print(f"   🔗 URL: http://localhost:3000{url}")
                    print()
                
                print("📋 INSTRUCCIONES DE ACCESO:")
                print("=" * 40)
                print("1. Ve a: http://localhost:3000")
                print("2. Inicia sesión con:")
                print("   • Usuario: admin")
                print("   • Contraseña: gridbot123")
                print("3. Busca el dashboard por nombre o usa los enlaces directos")
                print()
                
                print("🎯 DASHBOARDS PRINCIPALES:")
                print("=" * 30)
                
                # Buscar dashboards específicos
                gridbot_dashboards = [d for d in dashboards if 'GridBot' in d.get('title', '')]
                
                if gridbot_dashboards:
                    print("🤖 Dashboards de GridBot:")
                    for dashboard in gridbot_dashboards:
                        title = dashboard.get('title', '')
                        url = dashboard.get('url', '')
                        print(f"   • {title}")
                        print(f"     🔗 http://localhost:3000{url}")
                        print()
                
                # Buscar otros dashboards útiles
                other_dashboards = [d for d in dashboards if 'GridBot' not in d.get('title', '')]
                
                if other_dashboards:
                    print("📊 Otros Dashboards:")
                    for dashboard in other_dashboards:
                        title = dashboard.get('title', '')
                        url = dashboard.get('url', '')
                        print(f"   • {title}")
                        print(f"     🔗 http://localhost:3000{url}")
                        print()
                
                print("🔧 COMANDOS ÚTILES:")
                print("=" * 25)
                print("• Ver P&L actual: python3 check_pnl_simple.py")
                print("• Ver P&L detallado: docker-compose exec api python3 profit_loss_tracker.py")
                print("• Monitoreo continuo: docker-compose exec api python3 update_pnl_metrics.py --continuous")
                print("• Métricas Prometheus: http://localhost:9090")
                print("• API GridBot: http://localhost:8000/docs")
                
            else:
                print("❌ No se encontraron dashboards")
                
        else:
            print(f"❌ Error obteniendo dashboards: {result.stderr}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

def main():
    """Función principal"""
    list_grafana_dashboards()

if __name__ == "__main__":
    main() 