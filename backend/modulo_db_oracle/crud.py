"""
=============================================================================
MÓDULO CRUD - ORACLE DATABASE
=============================================================================
Sistema de conexión y consulta a Oracle con:
- Reconexión automática
- Queries externalizadas
- Soporte para nombre de operario
- Credenciales desde archivo .env
=============================================================================
"""

import jpype
import jaydebeapi
import time
import os
import logging
import threading
from typing import List, Dict, Optional
from .queries import get_query


class Datos:
    """
    Clase para gestionar conexiones a Oracle Database con reconexión automática.
    """
    
    # Configuración de conexión (se carga desde .env)
    JDBC_DRIVER = "oracle.jdbc.driver.OracleDriver"
    JDBC_URL = None
    USERNAME = None
    PASSWORD = None
    
    # Configuración de reconexión
    MAX_RETRIES = 3
    RETRY_DELAY_SECONDS = 2
    CONNECTION_TIMEOUT_SECONDS = 30
    
    @classmethod
    def _load_config(cls):
        """Carga la configuración desde .env"""
        try:
            # Intentar importar desde un nivel arriba
            import sys
            parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if parent_dir not in sys.path:
                sys.path.insert(0, parent_dir)
            
            from config import OracleConfig
            config = OracleConfig.get_config()
            cls.JDBC_URL = config['jdbc_url']
            cls.USERNAME = config['username']
            cls.PASSWORD = config['password']
            cls.JAR_PATH = config.get('jar_path', 'ojdbc8.jar')
            logging.info("✅ Configuración Oracle cargada desde .env")
        except ImportError as e:
            logging.warning(f"⚠️ No se pudo cargar config.py: {e}")
            # Fallback - sin credenciales (fallará al conectar)
            cls.JDBC_URL = ""
            cls.USERNAME = ""
            cls.PASSWORD = ""
            cls.JAR_PATH = "ojdbc8.jar"
    
    def __init__(self):
        """Inicializa la conexión a Oracle Database"""
        # Cargar configuración si no está cargada
        if self.JDBC_URL is None:
            self._load_config()
        
        self.conn = None
        self.cursor = None
        self._lock = threading.Lock() # Añadir lock para concurrencia
        self._connect()
    
    def _start_jvm_if_needed(self) -> bool:
        """Inicia la JVM si no está iniciada"""
        try:
            if not jpype.isJVMStarted():
                # Determinar ruta del JAR (manejar PyInstaller)
                import sys
                if getattr(sys, 'frozen', False):
                    # En el ejecutable, el JAR está en la raíz de _MEIPASS
                    ojdbc_jar_path = os.path.join(sys._MEIPASS, "ojdbc8.jar")
                else:
                    # En desarrollo, el JAR está en el directorio backend
                    # Intentamos encontrarlo en el directorio actual o en el padre
                    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                    ojdbc_jar_path = os.path.join(base_dir, "ojdbc8.jar")

                logging.info(f"📦 JAR path: {ojdbc_jar_path}")
                
                if not os.path.exists(ojdbc_jar_path):
                    logging.error(f"❌ No se encontró el archivo JAR: {ojdbc_jar_path}")
                    # Intentar fallback al directorio actual literal
                    ojdbc_jar_path = os.path.abspath("ojdbc8.jar")
                    if not os.path.exists(ojdbc_jar_path):
                         return False
                
                jpype.startJVM(classpath=[ojdbc_jar_path])
                logging.info("✅ JVM started")
            return True
        except Exception as e:
            logging.error(f"❌ Error iniciando JVM: {e}")
            return False
    
    def _connect(self) -> bool:
        """Versión pública de conexión"""
        with self._lock:
            return self._connect_internal()

    def _connect_internal(self) -> bool:
        """Establece la conexión. DEBE LLAMARSE CON LOCK."""
        try:
            if not self._start_jvm_if_needed():
                return False
            
            # Cerrar conexión anterior si existe
            self._close_quietly_internal()
            
            logging.info(f"🔗 Estableciendo conexión con base de datos de usuarios (Oracle)...")
            
            # Nueva conexión
            self.conn = jaydebeapi.connect(
                Datos.JDBC_DRIVER, 
                Datos.JDBC_URL, 
                [Datos.USERNAME, Datos.PASSWORD]
            )
            self.cursor = self.conn.cursor()
            logging.info("✅ Conexión Oracle establecida")
            return True
            
        except jaydebeapi.DatabaseError as e:
            logging.error(f"❌ Error en la conexión JDBC: {e}")
            self.conn = None
            self.cursor = None
            return False
        except Exception as e:
            logging.error(f"❌ Error inesperado al conectar: {e}")
            self.conn = None
            self.cursor = None
            return False

    def _close_quietly(self):
        with self._lock:
            self._close_quietly_internal()

    def _close_quietly_internal(self):
        """Versión interna sin lock"""
        try:
            if self.cursor:
                self.cursor.close()
        except: pass
        try:
            if self.conn:
                self.conn.close()
        except: pass
        self.cursor = None
        self.conn = None
    
    def _ensure_connection(self) -> bool:
        """Versión pública con lock (ya existente)"""
        with self._lock:
            return self._ensure_connection_locked()

    def _ensure_connection_locked(self) -> bool:
        """
        Verifica que la conexión esté activa, reconecta si es necesario.
        DEBE LLAMARSE CON EL LOCK YA ADQUIRIDO.
        """
        if self.conn is not None and self.cursor is not None:
            try:
                # Intento ligero de verificar el estado
                self.cursor.execute("SELECT 1 FROM DUAL") 
                self.cursor.fetchone()
                return True
            except:
                logging.warning("⚠️ La conexión Oracle parece perdida, intentando reconectar...")
        
        return self._reconnect_with_retry_locked()

    def _reconnect_with_retry_locked(self) -> bool:
        """Reconexión con reintentos. DEBE LLAMARSE CON LOCK."""
        for attempt in range(1, self.MAX_RETRIES + 1):
            logging.info(f"🔄 Intento de reconexión {attempt}/{self.MAX_RETRIES}...")
            
            # _connect() ya maneja su propio lock interno? no, lo quitaremos de ahí
            # para que _reconnect_with_retry_locked pueda llamarlo sin deadlock
            if self._connect_internal():
                logging.info(f"✅ Reconexión exitosa en intento {attempt}")
                return True
            
            if attempt < self.MAX_RETRIES:
                time.sleep(self.RETRY_DELAY_SECONDS)
        
        logging.error(f"❌ Falló la reconexión después de {self.MAX_RETRIES} intentos")
        return False
    
    def cerrar_conexion(self):
        """Cierra el cursor y la conexión a la base de datos"""
        try:
            if hasattr(self, 'cursor') and self.cursor:
                self.cursor.close()
            if hasattr(self, 'conn') and self.conn:
                self.conn.close()
            logging.info("✅ Conexión cerrada correctamente")
        except Exception as e:
            logging.error(f"❌ Error cerrando conexión: {e}")
    
    # =========================================================================
    # MÉTODOS PARA PACKING
    # =========================================================================
    
    def get_user_time_packing(self, include_nombre: bool = True) -> List[Dict]:
        """
        Obtiene usuarios activos en PACKING en los últimos 5 minutos.
        
        Args:
            include_nombre (bool): Si True, incluye el nombre del operario
        
        Returns:
            list: Lista de diccionarios con formato:
                [
                    {
                        'station': 'PACK-12',
                        'user': 'ABC123',          # código de usuario
                        'nombre': 'JUAN PEREZ',    # nombre del operario (si include_nombre=True)
                        'hora': '14:30'
                    },
                    ...
                ]
        """
        try:
            with self._lock:
                if not self._ensure_connection_locked():
                    logging.warning("⚠️ No hay conexión disponible para PACKING")
                    return []
                    
                query = get_query('packing', con_nombre=include_nombre)
                self.cursor.execute(query)
                rows = self.cursor.fetchall()
            
            if rows:
                logging.info(f"✅ Packing: {len(rows)} usuarios activos encontrados")
                
                if include_nombre:
                    lista_diccionarios = [
                        {
                            "station": str(puesto), 
                            "user": str(usuario),
                            "nombre": str(nombre),
                            "hora": str(hora)
                        }
                        for puesto, nombre, usuario, hora in rows
                    ]
                else:
                    lista_diccionarios = [
                        {
                            "station": str(station), 
                            "user": str(person), 
                            "hora": str(hora)
                        }
                        for station, person, hora in rows
                    ]
                return lista_diccionarios
            else:
                logging.info("ℹ️ Packing: No hay usuarios activos")
                return []

        except Exception as e:
            logging.error(f"❌ Error en PACKING: {e}")
            with self._lock:
                self.cursor = None # Forzar reconexión en el siguiente llamado
            return []
    
    # =========================================================================
    # MÉTODOS PARA RETURN
    # =========================================================================
    
    def get_user_time_return(self, include_nombre: bool = True) -> List[Dict]:
        """
        Obtiene usuarios activos en RETURN en los últimos 5 minutos.
        
        Args:
            include_nombre (bool): Si True, incluye el nombre del operario
        
        Returns:
            list: Lista de diccionarios con formato:
                [
                    {
                        'station': 'RET-5',
                        'user': 'ABC123',          # código de usuario
                        'nombre': 'MARIA GOMEZ',   # nombre del operario (si include_nombre=True)
                        'hora': '14:30'
                    },
                    ...
                ]
        """
        try:
            with self._lock:
                if not self._ensure_connection_locked():
                    logging.warning("⚠️ No hay conexión disponible para RETURN")
                    return []
                    
                query = get_query('return', con_nombre=include_nombre)
                self.cursor.execute(query)
                rows = self.cursor.fetchall()
            
            if rows:
                logging.info(f"✅ Return: {len(rows)} usuarios activos encontrados")
                
                if include_nombre:
                    lista_diccionarios = [
                        {
                            "station": str(puesto), 
                            "user": str(usuario),
                            "nombre": str(nombre),
                            "hora": str(hora)
                        }
                        for puesto, nombre, usuario, hora in rows
                    ]
                else:
                    lista_diccionarios = [
                        {
                            "station": str(station), 
                            "user": str(person), 
                            "hora": str(hora)
                        }
                        for station, person, hora in rows
                    ]
                return lista_diccionarios
            else:
                logging.info("ℹ️ Return: No hay usuarios activos")
                return []

        except Exception as e:
            logging.error(f"❌ Error en RETURN: {e}")
            with self._lock:
                self.cursor = None
            return []
    
    # =========================================================================
    # MÉTODOS PARA VAS
    # =========================================================================
    
    def get_user_time_vas(self, include_nombre: bool = True) -> List[Dict]:
        """
        Obtiene usuarios activos en VAS en los últimos 5 minutos.
        
        Args:
            include_nombre (bool): Si True, incluye el nombre del operario
        
        Returns:
            list: Lista de diccionarios con formato:
                [
                    {
                        'station': 'VAS-3',
                        'user': 'ABC123',          # código de usuario
                        'nombre': 'PEDRO LOPEZ',   # nombre del operario (si include_nombre=True)
                        'hora': '14:30'
                    },
                    ...
                ]
        """
        try:
            with self._lock:
                if not self._ensure_connection_locked():
                    logging.warning("⚠️ No hay conexión disponible para VAS")
                    return []
                    
                query = get_query('vas', con_nombre=include_nombre)
                self.cursor.execute(query)
                rows = self.cursor.fetchall()
            
            if rows:
                logging.info(f"✅ VAS: {len(rows)} usuarios activos encontrados")
                
                if include_nombre:
                    lista_diccionarios = [
                        {
                            "station": str(station), 
                            "user": str(usuario),
                            "nombre": str(nombre),
                            "hora": str(hora)
                        }
                        for station, nombre, usuario, hora in rows
                    ]
                else:
                    lista_diccionarios = [
                        {
                            "station": str(station), 
                            "user": str(person), 
                            "hora": str(hora)
                        }
                        for station, person, hora in rows
                    ]
                return lista_diccionarios
            else:
                logging.info("ℹ️ VAS: No hay usuarios activos")
                return []

        except Exception as e:
            logging.error(f"❌ Error en VAS: {e}")
            with self._lock:
                self.cursor = None
            return []
    
    # =========================================================================
    # MÉTODO COMBINADO
    # =========================================================================
    
    def get_all_active_users(self, include_nombre: bool = True) -> Dict:
        """
        Obtiene todos los usuarios activos de todos los departamentos.
        
        Args:
            include_nombre (bool): Si True, incluye el nombre del operario
        
        Returns:
            dict: Diccionario con usuarios por departamento:
                {
                    'packing': [{station, user, nombre, hora}, ...],
                    'return': [{station, user, nombre, hora}, ...],
                    'vas': [{station, user, nombre, hora}, ...]
                }
        """
        return {
            'packing': self.get_user_time_packing(include_nombre),
            'return': self.get_user_time_return(include_nombre),
            'vas': self.get_user_time_vas(include_nombre)
        }
    
    # =========================================================================
    # HEALTH CHECK
    # =========================================================================
    
    def is_connected(self) -> bool:
        """Verifica si hay conexión activa (con lock)"""
        with self._lock:
            try:
                if self.cursor is None or self.conn is None:
                    return False
                self.cursor.execute("SELECT 1 FROM DUAL")
                self.cursor.fetchone()
                return True
            except:
                return False
    
    def reconnect(self) -> bool:
        """Fuerza reconexión (con lock)"""
        with self._lock:
            logging.info("🔄 Forzando reconexión a Oracle...")
            return self._reconnect_with_retry_locked()
