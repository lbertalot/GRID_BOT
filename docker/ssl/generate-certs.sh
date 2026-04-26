#!/bin/bash

# Script para generar certificados TLS autofirmados para GridBot
# Uso: ./generate-certs.sh

set -e

SSL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CERT_DIR="$SSL_DIR/certs"

echo "🔐 Generando certificados TLS autofirmados para GridBot..."

# Crear directorio de certificados
mkdir -p "$CERT_DIR"

# Generar clave privada CA
openssl genrsa -out "$CERT_DIR/ca-key.pem" 4096

# Generar certificado CA
openssl req -new -x509 -days 365 -key "$CERT_DIR/ca-key.pem" -sha256 -out "$CERT_DIR/ca.pem" \
    -subj "/C=ES/ST=Madrid/L=Madrid/O=GridBot/OU=Dev/CN=GridBot-CA"

# Generar clave privada del servidor
openssl genrsa -out "$CERT_DIR/server-key.pem" 4096

# Generar CSR del servidor
openssl req -subj "/CN=gridbot.local" -sha256 -new -key "$CERT_DIR/server-key.pem" -out "$CERT_DIR/server.csr"

# Crear archivo de configuración para extensiones
cat > "$CERT_DIR/extfile.cnf" <<EOF
subjectAltName = DNS:gridbot.local,DNS:localhost,IP:127.0.0.1,IP:0.0.0.0
extendedKeyUsage = serverAuth
EOF

# Firmar certificado del servidor
openssl x509 -req -days 365 -sha256 -in "$CERT_DIR/server.csr" -CA "$CERT_DIR/ca.pem" \
    -CAkey "$CERT_DIR/ca-key.pem" -CAcreateserial -out "$CERT_DIR/server-cert.pem" \
    -extfile "$CERT_DIR/extfile.cnf"

# Generar clave privada del cliente
openssl genrsa -out "$CERT_DIR/client-key.pem" 4096

# Generar CSR del cliente
openssl req -subj "/CN=gridbot-client" -new -key "$CERT_DIR/client-key.pem" -out "$CERT_DIR/client.csr"

# Crear archivo de configuración para extensiones del cliente
cat > "$CERT_DIR/extfile-client.cnf" <<EOF
extendedKeyUsage = clientAuth
EOF

# Firmar certificado del cliente
openssl x509 -req -days 365 -sha256 -in "$CERT_DIR/client.csr" -CA "$CERT_DIR/ca.pem" \
    -CAkey "$CERT_DIR/ca-key.pem" -CAcreateserial -out "$CERT_DIR/client-cert.pem" \
    -extfile "$CERT_DIR/extfile-client.cnf"

# Limpiar archivos temporales
rm -f "$CERT_DIR/server.csr" "$CERT_DIR/client.csr" "$CERT_DIR/extfile.cnf" "$CERT_DIR/extfile-client.cnf"

# Configurar permisos
chmod 600 "$CERT_DIR"/*.pem
chmod 644 "$CERT_DIR/ca.pem"

echo "✅ Certificados TLS generados exitosamente:"
echo "   📁 CA Certificate: $CERT_DIR/ca.pem"
echo "   📁 Server Certificate: $CERT_DIR/server-cert.pem"
echo "   📁 Server Key: $CERT_DIR/server-key.pem"
echo "   📁 Client Certificate: $CERT_DIR/client-cert.pem"
echo "   📁 Client Key: $CERT_DIR/client-key.pem"
echo ""
echo "🔧 Para usar TLS en producción:"
echo "   1. Copia los certificados a los directorios correspondientes"
echo "   2. Actualiza las configuraciones de Prometheus y Alertmanager"
echo "   3. Configura Nginx para usar SSL"
echo ""
echo "⚠️  NOTA: Estos son certificados autofirmados para desarrollo."
echo "   Para producción, usa certificados de Let's Encrypt o una CA confiable."
