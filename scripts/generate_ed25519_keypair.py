#!/usr/bin/env python3
"""
Genera un par de claves Ed25519 para la WebSocket API de Binance.

Uso:
    python scripts/generate_ed25519_keypair.py [--out-dir secrets] [--name binance_ed25519]

Salida:
    <out-dir>/<name>.pem           → clave PRIVADA (PKCS8, sin passphrase)
    <out-dir>/<name>.pub.pem       → clave PÚBLICA (SubjectPublicKeyInfo)

Después:
    1. Sube la clave PÚBLICA (.pub.pem) a tu cuenta de Binance:
         Account → API Management → Create API → Ed25519 → pega el contenido
         del archivo .pub.pem (o el raw base64) → nombra la key → habilita
         permisos Spot Trading y Read. Copia la API Key que Binance te da.

    2. Configura las variables de entorno del bot:
         BINANCE_ED25519_API_KEY=<API key que te dio Binance>
         BINANCE_ED25519_PRIVATE_KEY_PATH=/ruta/absoluta/a/binance_ed25519.pem

    3. **NUNCA** commitees la clave privada. Añade el directorio de secrets
       al .gitignore y considera montarlo como volumen Docker en lectura.

Este script no envía nada a Binance; solo crea los archivos localmente.
"""

from __future__ import annotations

import argparse
import os
import stat
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def generate(out_dir: Path, name: str, force: bool) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    priv_path = out_dir / f"{name}.pem"
    pub_path = out_dir / f"{name}.pub.pem"

    if (priv_path.exists() or pub_path.exists()) and not force:
        print(
            f"❌ Ya existen archivos en {out_dir}/{name}.*. "
            f"Usa --force para sobreescribir.",
            file=sys.stderr,
        )
        sys.exit(2)

    private_key = Ed25519PrivateKey.generate()

    priv_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    priv_path.write_bytes(priv_pem)
    pub_path.write_bytes(pub_pem)

    # Permisos 600 sobre la clave privada (best-effort; no falla en Windows).
    try:
        os.chmod(priv_path, stat.S_IRUSR | stat.S_IWUSR)
    except Exception:
        pass

    return priv_path, pub_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Genera par de claves Ed25519 para Binance WS API v3."
    )
    parser.add_argument(
        "--out-dir",
        default="secrets",
        help="Directorio destino (relativo al cwd). Default: secrets/",
    )
    parser.add_argument(
        "--name",
        default="binance_ed25519",
        help="Nombre base de los archivos. Default: binance_ed25519",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Sobreescribir si los archivos ya existen.",
    )
    args = parser.parse_args()

    out_dir = Path(args.out_dir).resolve()
    priv_path, pub_path = generate(out_dir, args.name, args.force)

    print("✅ Par de claves Ed25519 generado.\n")
    print(f"🔐 Clave privada : {priv_path}   (permisos 600)")
    print(f"🔓 Clave pública : {pub_path}\n")
    print("Próximos pasos:")
    print(
        f"  1. Sube el contenido de {pub_path.name} a Binance → API Management (Ed25519)."
    )
    print("  2. Copia la API Key que te devuelve Binance.")
    print("  3. Exporta las variables de entorno:")
    print("       export BINANCE_ED25519_API_KEY=<tu_api_key>")
    print(f"       export BINANCE_ED25519_PRIVATE_KEY_PATH={priv_path}")
    print("  4. Reinicia los servicios (docker compose restart api worker beat).")
    print("\n⚠️  Nunca commitees la clave privada. Añade el directorio a .gitignore.")


if __name__ == "__main__":
    main()
