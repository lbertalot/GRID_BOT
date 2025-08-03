#!/usr/bin/env python3
"""
Script de diagnóstico para Redis
Verifica la conectividad y configuración de Redis
"""

import redis
import socket
import subprocess
import sys
from datetime import datetime

def check_redis_connectivity():
    """Verifica la conectividad con Redis"""
    print("🔍 Diagnóstico de Redis - GridBot Trading Platform")
    print("=" * 50)
    
    # Verificar puerto 6379
    print("📊 Verificando puerto 6379...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('localhost', 6379))
        sock.close()
        
        if result == 0:
            print("✅ Puerto 6379 está abierto")
        else:
            print("❌ Puerto 6379 está cerrado")
            return False
    except Exception as e:
        print(f"❌ Error verificando puerto 6379: {e}")
        return False
    
    # Verificar puerto 6380 (por si acaso)
    print("📊 Verificando puerto 6380...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('localhost', 6380))
        sock.close()
        
        if result == 0:
            print("⚠️  Puerto 6380 está abierto (no debería)")
        else:
            print("✅ Puerto 6380 está cerrado (correcto)")
    except Exception as e:
        print(f"❌ Error verificando puerto 6380: {e}")
    
    # Intentar conectar con Redis
    print("\n🔗 Intentando conectar con Redis...")
    try:
        r = redis.Redis(host='localhost', port=6379, db=0, socket_timeout=5)
        r.ping()
        print("✅ Conexión exitosa con Redis en puerto 6379")
        
        # Verificar información del servidor
        info = r.info()
        print(f"📊 Versión de Redis: {info.get('redis_version', 'N/A')}")
        print(f"📊 Puerto de escucha: {info.get('tcp_port', 'N/A')}")
        print(f"📊 Conexiones activas: {info.get('connected_clients', 'N/A')}")
        print(f"📊 Memoria usada: {info.get('used_memory_human', 'N/A')}")
        
        return True
    except redis.ConnectionError as e:
        print(f"❌ Error de conexión con Redis: {e}")
        return False
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        return False

def check_docker_redis():
    """Verifica el estado de Redis en Docker"""
    print("\n🐳 Verificando Redis en Docker...")
    
    try:
        # Verificar si el contenedor está ejecutándose
        result = subprocess.run(
            ['docker', 'ps', '--filter', 'name=gridbot_redis', '--format', '{{.Names}}:{{.Status}}'],
            capture_output=True, text=True, timeout=10
        )
        
        if result.returncode == 0 and result.stdout.strip():
            print("✅ Contenedor Redis está ejecutándose")
            print(f"📊 Estado: {result.stdout.strip()}")
        else:
            print("❌ Contenedor Redis no está ejecutándose")
            return False
        
        # Verificar logs de Redis
        print("\n📄 Últimos logs de Redis:")
        result = subprocess.run(
            ['docker-compose', 'logs', '--tail=10', 'redis'],
            capture_output=True, text=True, timeout=10
        )
        
        if result.returncode == 0:
            print(result.stdout)
        else:
            print("❌ No se pudieron obtener los logs")
        
        return True
    except subprocess.TimeoutExpired:
        print("❌ Timeout al verificar Docker")
        return False
    except Exception as e:
        print(f"❌ Error verificando Docker: {e}")
        return False

def check_redis_config():
    """Verifica la configuración de Redis"""
    print("\n⚙️  Verificando configuración de Redis...")
    
    try:
        r = redis.Redis(host='localhost', port=6379, db=0, socket_timeout=5)
        
        # Verificar configuración
        config = r.config_get('*')
        
        print("📋 Configuración de Redis:")
        print(f"   • Puerto: {config.get('port', 'N/A')}")
        print(f"   • Bind: {config.get('bind', 'N/A')}")
        print(f"   • Maxmemory: {config.get('maxmemory', 'N/A')}")
        print(f"   • Maxmemory-policy: {config.get('maxmemory-policy', 'N/A')}")
        print(f"   • Appendonly: {config.get('appendonly', 'N/A')}")
        
        return True
    except Exception as e:
        print(f"❌ Error obteniendo configuración: {e}")
        return False

def main():
    """Función principal"""
    print(f"🚀 Diagnóstico iniciado: {datetime.now()}")
    
    # Verificar conectividad
    redis_ok = check_redis_connectivity()
    
    # Verificar Docker
    docker_ok = check_docker_redis()
    
    # Verificar configuración
    config_ok = check_redis_config()
    
    # Resumen
    print("\n" + "=" * 50)
    print("📊 RESUMEN DEL DIAGNÓSTICO:")
    print(f"   • Conectividad: {'✅ OK' if redis_ok else '❌ ERROR'}")
    print(f"   • Docker: {'✅ OK' if docker_ok else '❌ ERROR'}")
    print(f"   • Configuración: {'✅ OK' if config_ok else '❌ ERROR'}")
    
    if redis_ok and docker_ok and config_ok:
        print("\n🎉 ¡Redis está funcionando correctamente!")
        return 0
    else:
        print("\n⚠️  Se detectaron problemas con Redis")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 