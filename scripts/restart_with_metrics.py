#!/usr/bin/env python3
"""
Script para reiniciar la API con métricas preconfiguradas
"""

import subprocess
import time

def restart_api_with_metrics():
    """Reinicia la API con métricas preconfiguradas"""
    try:
        print("🔄 Reiniciando API con métricas preconfiguradas...")
        
        # Detener la API
        subprocess.run(['docker-compose', 'stop', 'api'], check=True)
        print("✅ API detenida")
        
        # Esperar un momento
        time.sleep(2)
        
        # Iniciar la API
        subprocess.run(['docker-compose', 'start', 'api'], check=True)
        print("✅ API iniciada")
        
        # Esperar a que la API esté lista
        print("⏳ Esperando a que la API esté lista...")
        time.sleep(10)
        
        # Ejecutar métricas
        print("🚀 Ejecutando métricas...")
        result = subprocess.run([
            'docker', 'exec', 'gridbot_api', 'python', '/app/direct_metrics.py'
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Métricas ejecutadas exitosamente")
            print(f"📄 Salida: {result.stdout}")
        else:
            print(f"❌ Error ejecutando métricas: {result.stderr}")
            
        print("\n🌐 Verifica el dashboard en: http://localhost:3000")
        print("   Usuario: admin")
        print("   Contraseña: admin")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    restart_api_with_metrics() 