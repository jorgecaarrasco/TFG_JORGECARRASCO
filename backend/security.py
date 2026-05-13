"""
=============================================================================
MÓDULO DE SEGURIDAD - Dashboard de Control IT
=============================================================================
Funciones de seguridad para:
- Hash de contraseñas (SHA256 con salt)
- Verificación de contraseñas
- Generación de tokens seguros
=============================================================================
"""

import hashlib
import secrets
import os
from typing import Optional


def get_password_salt() -> str:
    """
    Obtiene el salt para contraseñas desde las variables de entorno.
    Si no existe, usa un salt por defecto (menos seguro).
    """
    try:
        from config import get_config
        salt = get_config('PASSWORD_SALT', '')
        if salt and salt != 'CAMBIA_ESTO_POR_UN_SALT_UNICO':
            return salt
    except ImportError:
        pass
    
    # Salt por defecto (cambiar en producción)
    return 'DEMO_DEFAULT_SALT_2026'


def hash_password(password: str, salt: str = None) -> str:
    """
    Genera un hash SHA256 de la contraseña con salt.
    
    Args:
        password: Contraseña en texto plano
        salt: Salt personalizado (opcional, usa el global si no se proporciona)
        
    Returns:
        str: Hash hexadecimal de 64 caracteres
    """
    if salt is None:
        salt = get_password_salt()
    
    # Combinar salt + password y hacer hash
    salted_password = f"{salt}{password}{salt}"
    hash_obj = hashlib.sha256(salted_password.encode('utf-8'))
    return hash_obj.hexdigest()


def verify_password(password: str, password_hash: str, salt: str = None) -> bool:
    """
    Verifica si una contraseña coincide con su hash.
    
    Args:
        password: Contraseña en texto plano a verificar
        password_hash: Hash almacenado
        salt: Salt personalizado (opcional)
        
    Returns:
        bool: True si coincide, False si no
    """
    computed_hash = hash_password(password, salt)
    return secrets.compare_digest(computed_hash, password_hash)


def generate_secure_password(length: int = 12) -> str:
    """
    Genera una contraseña segura aleatoria.
    
    Args:
        length: Longitud de la contraseña (mínimo 8)
        
    Returns:
        str: Contraseña segura
    """
    if length < 8:
        length = 8
    
    # Caracteres permitidos
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def generate_secret_key() -> str:
    """
    Genera una clave secreta segura para Flask.
    
    Returns:
        str: Clave hexadecimal de 64 caracteres
    """
    return secrets.token_hex(32)


def generate_salt() -> str:
    """
    Genera un salt seguro para hash de contraseñas.
    
    Returns:
        str: Salt hexadecimal de 32 caracteres
    """
    return secrets.token_hex(16)


def is_password_hashed(password: str) -> bool:
    """
    Detecta si una contraseña ya está hasheada (es un hash SHA256).
    
    Args:
        password: String a verificar
        
    Returns:
        bool: True si parece un hash SHA256
    """
    # SHA256 produce 64 caracteres hexadecimales
    if len(password) != 64:
        return False
    
    try:
        int(password, 16)
        return True
    except ValueError:
        return False


# =============================================================================
# MIGRACIÓN DE CONTRASEÑAS
# =============================================================================

def migrate_password_if_needed(stored_password: str, plain_password: str) -> Optional[str]:
    """
    Verifica si una contraseña almacenada necesita migración a hash.
    
    Si stored_password es texto plano y coincide con plain_password,
    devuelve el hash para actualizar la base de datos.
    
    Args:
        stored_password: Contraseña almacenada en BD
        plain_password: Contraseña introducida por el usuario
        
    Returns:
        str: Nuevo hash si necesita migración, None si no
    """
    # Si ya está hasheada, no migrar
    if is_password_hashed(stored_password):
        return None
    
    # Si la contraseña en texto plano coincide, devolver el hash
    if stored_password == plain_password:
        return hash_password(plain_password)
    
    return None


# =============================================================================
# UTILIDADES
# =============================================================================

if __name__ == '__main__':
    # Herramienta de línea de comandos para generar claves
    print("=" * 60)
    print("🔐 Security Key Generator")
    print("=" * 60)
    print()
    print("📌 Clave secreta para Flask (FLASK_SECRET_KEY):")
    print(f"   {generate_secret_key()}")
    print()
    print("📌 Salt para contraseñas (PASSWORD_SALT):")
    print(f"   {generate_salt()}")
    print()
    print("📌 Contraseña segura de ejemplo:")
    print(f"   {generate_secure_password(16)}")
    print()
    print("⚠️  Copia estos valores a tu archivo .env")
    print("=" * 60)
