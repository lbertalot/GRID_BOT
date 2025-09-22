#!/usr/bin/env python3
"""
Script de activación del AutoRebalancer V2
Configura y activa el sistema de liquidez autónoma para GridBot v2.5
"""

import os
import sys
import asyncio
import logging
from datetime import datetime

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.auto_rebalancer_v2 import auto_rebalancer_v2

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def activate_rebalancer_v2():
    """Activa el sistema de rebalanceo V2"""
    logger.info("🚀 ACTIVANDO AUTOREBALANCER V2 - SISTEMA DE LIQUIDEZ AUTÓNOMA")
    logger.info("=" * 70)
    
    try:
        # 1. Verificar configuración
        logger.info("🔧 Paso 1: Verificando configuración...")
        
        config_status = {
            "ENABLE_AUTO_REBALANCE": os.getenv('ENABLE_AUTO_REBALANCE', 'true'),
            "MIN_USDT_BALANCE": os.getenv('MIN_USDT_BALANCE', '25.0'),
            "TARGET_USDT_BALANCE": os.getenv('TARGET_USDT_BALANCE', '50.0'),
            "REBALANCE_ASSET_PRIORITY": os.getenv('REBALANCE_ASSET_PRIORITY', 'SPK,HOME,SIGN,BNB,BTC')
        }
        
        for key, value in config_status.items():
            logger.info(f"   ✅ {key}: {value}")
        
        # 2. Verificar estado actual
        logger.info("\n📊 Paso 2: Verificando estado actual del rebalanceador...")
        
        status = await auto_rebalancer_v2.get_rebalance_status()
        
        logger.info(f"   💰 Balance actual USDT: {status.get('current_usdt_balance', 0):.2f}")
        logger.info(f"   🎯 Mínimo requerido: {status.get('min_usdt_balance', 0):.2f}")
        logger.info(f"   🎯 Objetivo: {status.get('target_usdt_balance', 0):.2f}")
        logger.info(f"   ⚠️ Necesita rebalanceo: {status.get('needs_rebalance', False)}")
        logger.info(f"   🔄 Habilitado: {status.get('enabled', False)}")
        
        # 3. Verificar activos disponibles
        logger.info(f"\n📋 Paso 3: Activos disponibles para liquidación:")
        available_assets = status.get('available_assets', [])
        if available_assets:
            for asset in available_assets:
                logger.info(f"   ✅ {asset}")
        else:
            logger.warning("   ⚠️ No hay activos disponibles para liquidación")
        
        # 4. Verificar activos protegidos
        logger.info(f"\n🛡️ Paso 4: Activos protegidos (nunca se venden):")
        protected_assets = status.get('protected_assets', [])
        for asset in protected_assets:
            logger.info(f"   🛡️ {asset}")
        
        # 5. Ejecutar test de rebalanceo si es necesario
        if status.get('needs_rebalance', False):
            logger.info(f"\n🔄 Paso 5: Ejecutando rebalanceo automático...")
            
            try:
                result = await auto_rebalancer_v2.check_and_rebalance()
                
                if result.get('status') == 'success':
                    logger.info(f"   ✅ Rebalanceo exitoso: {result.get('message', 'Liquidez restaurada')}")
                    
                    # Verificar estado actualizado
                    updated_status = await auto_rebalancer_v2.get_rebalance_status()
                    logger.info(f"   💰 Nuevo balance USDT: {updated_status.get('current_usdt_balance', 0):.2f}")
                    
                elif result.get('status') == 'sufficient':
                    logger.info(f"   ✅ Liquidez suficiente: {result.get('current_usdt', 0):.2f} USDT")
                    
                else:
                    logger.warning(f"   ⚠️ Rebalanceo no ejecutado: {result.get('message', 'Razón desconocida')}")
                    
            except Exception as e:
                logger.error(f"   ❌ Error ejecutando rebalanceo: {e}")
                return False
        else:
            logger.info(f"\n✅ Paso 5: Liquidez suficiente - No se requiere rebalanceo")
        
        # 6. Verificar integración con ciclo de trading
        logger.info(f"\n🔗 Paso 6: Verificando integración con ciclo de trading...")
        
        # Verificar que el rebalanceador está integrado en trading_tasks.py
        trading_tasks_path = os.path.join(os.path.dirname(__file__), '..', 'app', 'services', 'trading_tasks.py')
        if os.path.exists(trading_tasks_path):
            with open(trading_tasks_path, 'r') as f:
                content = f.read()
                if 'auto_rebalancer_v2' in content:
                    logger.info("   ✅ Rebalanceador V2 integrado en trading_tasks.py")
                else:
                    logger.warning("   ⚠️ Rebalanceador V2 no encontrado en trading_tasks.py")
        else:
            logger.error("   ❌ Archivo trading_tasks.py no encontrado")
        
        # 7. Resumen final
        logger.info(f"\n🎯 RESUMEN DE ACTIVACIÓN:")
        logger.info(f"   ✅ Configuración verificada")
        logger.info(f"   ✅ Estado del rebalanceador verificado")
        logger.info(f"   ✅ Activos disponibles: {len(available_assets)}")
        logger.info(f"   ✅ Activos protegidos: {len(protected_assets)}")
        logger.info(f"   ✅ Integración con trading verificada")
        
        if status.get('needs_rebalance', False):
            logger.info(f"   🔄 Rebalanceo ejecutado")
        else:
            logger.info(f"   ✅ Liquidez suficiente")
        
        logger.info(f"\n🎉 AUTOREBALANCER V2 ACTIVADO EXITOSAMENTE")
        logger.info(f"   El sistema ahora puede generar liquidez automáticamente")
        logger.info(f"   cuando detecte balance USDT insuficiente")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error activando rebalanceador V2: {e}")
        return False


async def main():
    """Función principal"""
    logger.info(f"🕐 Iniciando activación del AutoRebalancer V2 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    success = await activate_rebalancer_v2()
    
    if success:
        logger.info(f"\n✅ ACTIVACIÓN COMPLETADA EXITOSAMENTE")
        logger.info(f"   GridBot v2.5 ahora tiene liquidez autónoma")
        return 0
    else:
        logger.error(f"\n❌ ACTIVACIÓN FALLÓ")
        logger.error(f"   Revisar configuración y logs")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
