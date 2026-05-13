"""
=============================================================================
MÓDULO DE CONFIGURACIÓN - Dashboard de Control
=============================================================================
Carga configuración desde archivo .env de forma segura
=============================================================================
"""

import os
from pathlib import Path
from typing import Optional

import sys
# Ruta del directorio actual, manejando el empaquetado de PyInstaller
if getattr(sys, 'frozen', False):
    # Si es un ejecutable, BASE_DIR es la carpeta donde está el .exe
    BASE_DIR = Path(sys.executable).parent
    # Pero si necesitamos archivos empaquetados (como el frontend), usamos sys._MEIPASS
    BUNDLE_DIR = Path(sys._MEIPASS)
else:
    BASE_DIR = Path(__file__).resolve().parent
    BUNDLE_DIR = BASE_DIR

def load_env_file(env_path: str = None) -> dict:
    """
    Carga variables de entorno desde un archivo .env
    
    Args:
        env_path: Ruta al archivo .env (opcional)
        
    Returns:
        dict: Diccionario con las variables cargadas
    """
    if env_path is None:
        env_path = BASE_DIR / '.env'
    else:
        env_path = Path(env_path)
    
    config = {}
    
    if not env_path.exists():
        print(f"[!] Archivo de configuración no encontrado: {env_path}")
        print("[i] Copia .env.example a .env y configura tus credenciales")
        return config
    
    try:
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                
                # Ignorar comentarios y líneas vacías
                if not line or line.startswith('#'):
                    continue
                
                # Parsear KEY=VALUE
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    # Remover comillas si las tiene
                    if (value.startswith('"') and value.endswith('"')) or \
                       (value.startswith("'") and value.endswith("'")):
                        value = value[1:-1]
                    
                    config[key] = value
                    # También establecer como variable de entorno
                    os.environ[key] = value
        
        print(f"[OK] Configuración cargada desde: {env_path}")
        
    except Exception as e:
        print(f"[ERROR] Error cargando configuración: {e}")
    
    return config


def get_config(key: str, default: str = None) -> Optional[str]:
    """
    Obtiene un valor de configuración
    
    Args:
        key: Nombre de la variable
        default: Valor por defecto si no existe
        
    Returns:
        str: Valor de la configuración
    """
    return os.environ.get(key, default)


def get_config_int(key: str, default: int = 0) -> int:
    """Obtiene un valor de configuración como entero"""
    value = get_config(key, str(default))
    try:
        return int(value)
    except ValueError:
        return default


def get_config_bool(key: str, default: bool = False) -> bool:
    """Obtiene un valor de configuración como booleano"""
    value = get_config(key, str(default)).lower()
    return value in ('true', '1', 'yes', 'on')


# =============================================================================
# CONFIGURACIONES POR MÓDULO
# =============================================================================

class MySQLConfig:
    """Configuración de MySQL"""
    
    @staticmethod
    def get_config():
        return {
            'host': get_config('MYSQL_HOST', '127.0.0.1'),
            'port': get_config_int('MYSQL_PORT', 3306),
            'database': get_config('MYSQL_DATABASE', 'incidencias_dashboard'),
            'user': get_config('MYSQL_USER', 'root'),
            'password': get_config('MYSQL_PASSWORD', ''),
        }


class OracleConfig:
    """Configuración de Oracle"""
    
    @staticmethod
    def get_config():
        return {
            'jdbc_url': get_config('ORACLE_JDBC_URL', ''),
            'username': get_config('ORACLE_USERNAME', ''),
            'password': get_config('ORACLE_PASSWORD', ''),
            'jar_path': get_config('OJDBC_JAR_PATH', 'ojdbc8.jar'),
        }


class SQLiteConfig:
    """Configuración de SQLite"""
    
    @staticmethod
    def get_config():
        return {
            'database_path': get_config('SQLITE_DATABASE_PATH', str(BASE_DIR / 'database' / 'incidencias.db')),
        }


class FlaskConfig:
    """Configuración de Flask"""
    
    @staticmethod
    def get_config():
        return {
            'secret_key': get_config('FLASK_SECRET_KEY', 'change-this-secret-key'),
            'host': get_config('FLASK_HOST', '0.0.0.0'),
            'port': get_config_int('FLASK_PORT', 5000),
            'debug': get_config_bool('FLASK_DEBUG', False),
        }


class ServiceConfig:
    """Configuración de servicios externos"""
    
    @staticmethod
    def get_teamviewer_password():
        return get_config('TEAMVIEWER_PASSWORD', '')
    
    @staticmethod
    def get_ssh_config():
        return {
            'user': get_config('RFID_SSH_USER', 'root'),
            'password': get_config('RFID_SSH_PASSWORD', ''),
        }
    
    @staticmethod
    def get_cache_config():
        return {
            'user_cache_timeout': get_config_int('USER_CACHE_TIMEOUT', 300),
        }
    
    @staticmethod
    def get_timeout_config():
        return {
            'ssh_timeout': get_config_int('SSH_TIMEOUT', 10),
        }
    
    @staticmethod
    def get_thread_pool_config():
        return {
            'max_workers': get_config_int('THREAD_POOL_MAX_WORKERS', 10),
        }

class SSLConfig:
    """Configuración de SSL/HTTPS"""
    
    @staticmethod
    def is_enabled():
        return get_config_bool('SSL_ENABLED', False)
    
    @staticmethod
    def get_config():
        return {
            'enabled': get_config_bool('SSL_ENABLED', False),
            'cert_path': get_config('SSL_CERT_PATH', 'certs/cert.pem'),
            'key_path': get_config('SSL_KEY_PATH', 'certs/key.pem'),
        }
    
    @staticmethod
    def get_ssl_context():
        """Devuelve el contexto SSL para Flask, o None si no está habilitado"""
        if not SSLConfig.is_enabled():
            return None
        config = SSLConfig.get_config()
        return (config['cert_path'], config['key_path'])


class SecurityConfig:
    """Configuración de seguridad"""
    
    @staticmethod
    def get_password_salt():
        salt = get_config('PASSWORD_SALT', '')
        if not salt or salt == 'CAMBIA_ESTO_POR_UN_SALT_UNICO':
            return 'DEMO_DEFAULT_SALT_2026'  # Fallback (menos seguro)
        return salt


# Cargar configuración al importar el módulo
_config = load_env_file()

# Exportar funciones principales
__all__ = [
    'get_config',
    'get_config_int', 
    'get_config_bool',
    'MySQLConfig',
    'OracleConfig',
    'SQLiteConfig',
    'FlaskConfig',
    'ServiceConfig',
    'SSLConfig',
    'SecurityConfig',
    'load_env_file'
]
