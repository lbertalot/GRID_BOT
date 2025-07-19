import pytest
import os
from binance import Client
from binance.exceptions import BinanceAPIException

class TestBinanceDiagnostic:
    """Tests para diagnosticar problemas con Binance API"""
    
    @pytest.fixture
    def binance_client(self):
        """Fixture para crear cliente de Binance con credenciales reales"""
        api_key = os.getenv("BINANCE_API_KEY")
        api_secret = os.getenv("BINANCE_API_SECRET")
        
        if not api_key or not api_secret:
            pytest.skip("Credenciales de Binance no configuradas")
        
        return Client(api_key, api_secret)
    
    def test_binance_credentials_validity(self, binance_client):
        """Test para verificar si las credenciales son válidas"""
        try:
            # Intentar obtener información de la cuenta (requiere autenticación)
            account_info = binance_client.get_account()
            
            print(f"✅ Credenciales de Binance válidas")
            print(f"   Tipo de cuenta: {account_info.get('accountType', 'N/A')}")
            print(f"   Comisión maker: {account_info.get('makerCommission', 'N/A')}")
            print(f"   Comisión taker: {account_info.get('takerCommission', 'N/A')}")
            
            # Verificar balances
            balances = account_info['balances']
            non_zero_balances = [b for b in balances if float(b['free']) > 0 or float(b['locked']) > 0]
            
            print(f"   Balances con saldo: {len(non_zero_balances)}")
            for balance in non_zero_balances[:5]:  # Mostrar solo los primeros 5
                print(f"     {balance['asset']}: Libre={balance['free']}, Bloqueado={balance['locked']}")
            
            return True
            
        except BinanceAPIException as e:
            print(f"❌ Error de Binance API: {e}")
            print(f"   Código: {e.code}")
            print(f"   Mensaje: {e.message}")
            
            if e.code == -1022:
                print(f"   🔍 DIAGNÓSTICO: Problema de firma de API")
                print(f"   Posibles causas:")
                print(f"     1. API Key inválida")
                print(f"     2. API Secret incorrecto")
                print(f"     3. Permisos insuficientes en la API Key")
                print(f"     4. Restricciones de IP")
                print(f"     5. API Key deshabilitada")
            
            return False
            
        except Exception as e:
            print(f"❌ Error inesperado: {e}")
            return False
    
    def test_binance_api_key_permissions(self, binance_client):
        """Test para verificar permisos de la API Key"""
        try:
            # Intentar obtener información de la cuenta
            account_info = binance_client.get_account()
            
            print(f"✅ API Key tiene permisos de lectura")
            
            # Verificar si tiene permisos de trading
            try:
                # Intentar obtener órdenes abiertas (requiere permisos de trading)
                open_orders = binance_client.get_open_orders()
                print(f"✅ API Key tiene permisos de trading")
                print(f"   Órdenes abiertas: {len(open_orders)}")
                
            except BinanceAPIException as e:
                if e.code == -2015:
                    print(f"⚠️ API Key no tiene permisos de trading")
                else:
                    print(f"❌ Error verificando permisos de trading: {e}")
            
            return True
            
        except BinanceAPIException as e:
            print(f"❌ Error verificando permisos: {e}")
            return False
    
    def test_binance_connection_without_auth(self):
        """Test de conexión sin autenticación (endpoints públicos)"""
        try:
            # Crear cliente sin credenciales para endpoints públicos
            client = Client()
            
            # Probar endpoints públicos
            server_time = client.get_server_time()
            print(f"✅ Conexión a Binance exitosa (endpoints públicos)")
            print(f"   Tiempo del servidor: {server_time}")
            
            # Obtener información del exchange
            exchange_info = client.get_exchange_info()
            print(f"   Símbolos disponibles: {len(exchange_info['symbols'])}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error conectando a Binance: {e}")
            return False
    
    def test_binance_ip_restrictions(self, binance_client):
        """Test para verificar restricciones de IP"""
        try:
            # Intentar obtener información de la cuenta
            account_info = binance_client.get_account()
            
            print(f"✅ No hay restricciones de IP")
            return True
            
        except BinanceAPIException as e:
            if e.code == -1022:
                print(f"❌ Posible restricción de IP")
                print(f"   Verifica que tu IP esté en la lista blanca de Binance")
            else:
                print(f"❌ Error: {e}")
            return False
    
    def test_binance_api_key_status(self, binance_client):
        """Test para verificar el estado de la API Key"""
        try:
            # Intentar obtener información de la cuenta
            account_info = binance_client.get_account()
            
            print(f"✅ API Key está activa")
            return True
            
        except BinanceAPIException as e:
            if e.code == -1022:
                print(f"❌ API Key puede estar deshabilitada")
                print(f"   Verifica en el panel de Binance que la API Key esté activa")
            else:
                print(f"❌ Error: {e}")
            return False

if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 