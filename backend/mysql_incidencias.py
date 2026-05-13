"""
=============================================================================
MÓDULO DE GESTIÓN DE INCIDENCIAS - MySQL
=============================================================================
Base de datos: incidencias_dashboard
Versión: 2.0 - Nueva estructura
=============================================================================
"""

import pymysql
import logging
import threading
from datetime import datetime
from typing import List, Dict, Optional

class MySQLIncidencias:
    """
    Clase para gestionar incidencias en MySQL
    Base de datos: incidencias_dashboard
    Con reconexión automática y validación de conexión.
    """
    
    # ✅ Cargar configuración desde .env
    @classmethod
    def _load_db_config(cls):
        """Carga la configuración desde .env si está disponible"""
        try:
            from config import MySQLConfig
            config = MySQLConfig.get_config()
            return {
                'host': config['host'],
                'database': config['database'],
                'user': config['user'],
                'password': config['password'],
                'port': config['port'],
                'cursorclass': pymysql.cursors.DictCursor,
                'autocommit': False,
                'charset': 'utf8mb4',
                'connect_timeout': 10,
                'read_timeout': 30,
                'write_timeout': 30
            }
        except ImportError:
            # Fallback si config.py no está disponible
            return {
                'host': '127.0.0.1',
                'database': 'incidencias_dashboard',
                'user': 'root',
                'password': '',  # ⚠️ Configurar en .env
                'port': 3306,
                'cursorclass': pymysql.cursors.DictCursor,
                'autocommit': False,
                'charset': 'utf8mb4',
                'connect_timeout': 10,
                'read_timeout': 30,
                'write_timeout': 30
            }
    
    # Configuración de conexión (se carga dinámicamente)
    DB_CONFIG = None
    
    # Configuración de reconexión
    MAX_RETRIES = 3
    RETRY_DELAY_SECONDS = 2
    
    # ✅ RLock (reentrant) para evitar accesos concurrentes y permitir llamadas anidadas
    _lock = threading.RLock()
    
    def __init__(self):
        """
        Inicializa la conexión a MySQL con soporte para reconexión automática.
        Carga la configuración desde .env
        """
        # ✅ Cargar configuración dinámicamente
        if self.DB_CONFIG is None:
            self.DB_CONFIG = self._load_db_config()
        
        self.connection = None
        # self.cursor removed for thread safety
        self._connect()
    
    def _connect(self) -> bool:
        """
        Establece conexión a MySQL.
        
        Returns:
            bool: True si la conexión fue exitosa
        """
        try:
            # Cerrar conexión anterior si existe
            self._close_quietly()
            
            self.connection = pymysql.connect(**self.DB_CONFIG)
            
            if self.connection.open:
                # self.cursor = self.connection.cursor()  <-- REMOVED
                logging.info(f"✅ Conectado a MySQL Server (incidencias_dashboard)")
                return True
            
            return False
            
        except Exception as e:
            logging.error(f"❌ Error conectando a MySQL: {e}")
            self.connection = None
            self.cursor = None
            return False
    
    def _close_quietly(self):
        """Cierra la conexión sin lanzar excepciones"""
        try:
            # if self.cursor: self.cursor.close() <-- REMOVED
            pass
        except:
            pass
        try:
            if self.connection and self.connection.open:
                self.connection.close()
        except:
            pass
        # self.cursor = None
        self.connection = None
    
    def _ensure_connection(self) -> bool:
        """
        Verifica que la conexión esté activa, reconecta si es necesario.
        
        Returns:
            bool: True si hay conexión disponible
        """
        if self.connection is None:
            logging.warning("⚠️ Conexión MySQL perdida, intentando reconectar...")
            return self._reconnect_with_retry()
        
        # Verificar si la conexión sigue viva
        try:
            self.connection.ping(reconnect=True)
            return True
        except Exception as e:
            logging.warning(f"⚠️ Ping MySQL falló ({e}), reconectando...")
            return self._reconnect_with_retry()
    
    def _reconnect_with_retry(self) -> bool:
        """
        Intenta reconectar con reintentos.
        
        Returns:
            bool: True si se reconectó exitosamente
        """
        import time
        
        for attempt in range(1, self.MAX_RETRIES + 1):
            logging.info(f"🔄 MySQL: Intento de reconexión {attempt}/{self.MAX_RETRIES}...")
            
            if self._connect():
                logging.info(f"✅ MySQL: Reconexión exitosa en intento {attempt}")
                return True
            
            if attempt < self.MAX_RETRIES:
                time.sleep(self.RETRY_DELAY_SECONDS)
        
        logging.error(f"❌ MySQL: Falló la reconexión después de {self.MAX_RETRIES} intentos")
        return False
    
    def is_connected(self) -> bool:
        """
        Verifica si hay conexión activa a la base de datos.
        
        Returns:
            bool: True si hay conexión activa
        """
        try:
            if self.connection is None or not self.connection.open:
                return False
            self.connection.ping(reconnect=False)
            return True
        except:
            return False
    
    def reconnect(self) -> bool:
        """
        Fuerza una reconexión a la base de datos.
        
        Returns:
            bool: True si la reconexión fue exitosa
        """
        logging.info("🔄 Forzando reconexión a MySQL...")
        return self._reconnect_with_retry()
    
    def close(self):
        """Cierra la conexión"""
        try:
            # if self.cursor: self.cursor.close()
            if self.connection and self.connection.open:
                self.connection.close()
                logging.info("✅ Conexión MySQL cerrada")
        except Exception as e:
            logging.error(f"❌ Error cerrando conexión: {e}")
    
    # =========================================================================
    # MÉTODOS THREAD-SAFE PARA QUERIES
    # =========================================================================
    
    def _execute_query(self, query: str, params: tuple = None, fetch_all: bool = True):
        """
        Ejecuta una query de forma thread-safe con lock.
        
        Args:
            query: SQL query a ejecutar
            params: Parámetros para la query
            fetch_all: Si True, retorna fetchall(), si False retorna fetchone()
            
        Returns:
            Resultados de la query o None si falla
        """
        with self._lock:
            try:
                if not self._ensure_connection():
                    logging.error("❌ No hay conexión MySQL disponible")
                    return None
                
                with self.connection.cursor() as cursor:
                    cursor.execute(query, params or ())
                    
                    if fetch_all:
                        return cursor.fetchall()
                    else:
                        return cursor.fetchone()
                    
            except Exception as e:
                logging.error(f"❌ Error ejecutando query: {e}")
                return None
    
    def _execute_update(self, query: str, params: tuple = None, commit: bool = True) -> bool:
        """
        Ejecuta una query de actualización de forma thread-safe.
        
        Args:
            query: SQL query (INSERT, UPDATE, DELETE)
            params: Parámetros para la query
            commit: Si True, hace commit automático
            
        Returns:
            bool: True si se ejecutó correctamente
        """
        with self._lock:
            try:
                if not self._ensure_connection():
                    logging.error("❌ No hay conexión MySQL disponible")
                    return False
                
                with self.connection.cursor() as cursor:
                    cursor.execute(query, params or ())
                    
                    if commit:
                        self.connection.commit()
                    
                    return True
                    
            except Exception as e:
                logging.error(f"❌ Error ejecutando update: {e}")
                if commit:
                    try:
                        self.connection.rollback()
                    except:
                        pass
                return False
    
    # =========================================================================
    # MÉTODOS PARA INCIDENCIAS
    # =========================================================================
    
    def get_todas_incidencias(self) -> List[Dict]:
        """
        Obtiene todas las incidencias del sistema
        
        Returns:
            list: Lista de incidencias con formato completo
        """
        # ✅ USAR LOCK PARA THREAD-SAFETY
        with self._lock:
            # Asegurar conexión activa
            if not self._ensure_connection():
                logging.error("❌ No hay conexión MySQL disponible")
                return []
            
            try:
                query = """
                    SELECT 
                        i.id,
                        i.departamento,
                        i.puesto,
                        i.categoria,
                        i.descripcion,
                        i.prioridad,
                        i.estado,
                        i.reportado_por,
                        i.reportado_por_username,
                        i.resuelto_por,
                        i.fecha_creacion,
                        i.fecha_actualizacion,
                        i.fecha_resolucion,
                        i.notas_resolucion,
                        COUNT(c.id) as total_comentarios
                    FROM incidencias i
                    LEFT JOIN comentarios_incidencias c ON i.id = c.incidencia_id
                    GROUP BY i.id
                    ORDER BY 
                        FIELD(i.estado, 'pendiente', 'en_proceso', 'resuelta'),
                        i.fecha_creacion DESC
                """
                
                with self.connection.cursor() as cursor:
                    cursor.execute(query)
                    incidencias = cursor.fetchall()
                    
                    # Convertir fechas a formato ISO
                    for inc in incidencias:
                        inc['fecha_creacion'] = inc['fecha_creacion'].isoformat() if inc['fecha_creacion'] else None
                        inc['fecha_actualizacion'] = inc['fecha_actualizacion'].isoformat() if inc['fecha_actualizacion'] else None
                        inc['fecha_resolucion'] = inc['fecha_resolucion'].isoformat() if inc['fecha_resolucion'] else None
                        inc['comentarios'] = []  # Se pueden cargar bajo demanda
                
                    logging.info(f"✅ Obtenidas {len(incidencias)} incidencias")
                    return incidencias
                
            except Exception as e:
                logging.error(f"❌ Error obteniendo incidencias: {e}")
                return []
    
    def crear_incidencia(self, datos: Dict, reportado_por_nombre: str, reportado_por_username: str) -> Optional[Dict]:
        """
        Crea una nueva incidencia
        
        Args:
            datos (dict): Datos de la incidencia
            reportado_por_nombre (str): Nombre completo del usuario
            reportado_por_username (str): Username del usuario
            
        Returns:
            dict: Incidencia creada o None si falla
        """
        # ✅ USAR LOCK PARA THREAD-SAFETY
        with self._lock:
            # Asegurar conexión activa
            if not self._ensure_connection():
                logging.error("❌ No hay conexión MySQL disponible")
                return None
            
            try:
                # Extraer número de puesto
                puesto = datos.get('puesto', '')
                if isinstance(puesto, str) and '-' in puesto:
                    puesto_num = int(puesto.split('-')[1])
                else:
                    puesto_num = int(puesto)
                
                query = """
                    INSERT INTO incidencias 
                    (departamento, puesto, categoria, descripcion, prioridad, 
                     estado, reportado_por, reportado_por_username)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """
                
                values = (
                    datos.get('departamento', '').lower(),
                    puesto_num,
                    datos.get('categoria', ''),
                    datos.get('descripcion', ''),
                    datos.get('prioridad', 'MEDIA'),
                    'pendiente',  # Estado inicial
                    reportado_por_nombre,
                    reportado_por_username
                )
                
                with self.connection.cursor() as cursor:
                    cursor.execute(query, values)
                    self.connection.commit()
                    
                    incidencia_id = cursor.lastrowid
                    logging.info(f"✅ Incidencia creada: ID={incidencia_id}, Puesto={datos.get('departamento')}-{puesto_num}")
                    
                # ⚠️ NOTA: El evento de creación se registra automáticamente 
                # mediante el TRIGGER 'after_incidencia_insert' en MySQL
                # No es necesario insertarlo manualmente aquí
                
                # Obtener la incidencia recién creada
                return self.get_incidencia_por_id(incidencia_id)
                
            except Exception as e:
                logging.error(f"❌ Error creando incidencia: {e}")
                self.connection.rollback()
                return None
    
    def get_incidencia_por_id(self, incidencia_id: int) -> Optional[Dict]:
        """
        Obtiene una incidencia específica por ID
        
        Args:
            incidencia_id (int): ID de la incidencia
            
        Returns:
            dict: Incidencia o None
        """
        # ✅ USAR LOCK PARA THREAD-SAFETY
        with self._lock:
            try:
                if not self._ensure_connection():
                    return None
                    
                query = """
                    SELECT 
                        i.*,
                        COUNT(c.id) as total_comentarios
                    FROM incidencias i
                    LEFT JOIN comentarios_incidencias c ON i.id = c.incidencia_id
                    WHERE i.id = %s
                    GROUP BY i.id
                """
                
                with self.connection.cursor() as cursor:
                    cursor.execute(query, (incidencia_id,))
                    incidencia = cursor.fetchone()
                    
                    if incidencia:
                        # Convertir fechas a formato ISO
                        incidencia['fecha_creacion'] = incidencia['fecha_creacion'].isoformat() if incidencia['fecha_creacion'] else None
                        incidencia['fecha_actualizacion'] = incidencia['fecha_actualizacion'].isoformat() if incidencia['fecha_actualizacion'] else None
                        incidencia['fecha_resolucion'] = incidencia['fecha_resolucion'].isoformat() if incidencia['fecha_resolucion'] else None
                        
                if incidencia:
                    # Cargar comentarios (usando método aparte)
                    incidencia['comentarios'] = self.get_comentarios_incidencia(incidencia_id)
                    
                return incidencia
                
                return None
                
            except Exception as e:
                logging.error(f"❌ Error obteniendo incidencia {incidencia_id}: {e}")
                return None
    
    def actualizar_estado_incidencia(self, incidencia_id: int, nuevo_estado: str, 
                                    resuelto_por: str = None, notas: str = None,
                                    resuelto_por_username: str = None) -> Optional[Dict]:
        """
        Actualiza el estado de una incidencia
        
        Args:
            incidencia_id (int): ID de la incidencia
            nuevo_estado (str): Nuevo estado ('pendiente', 'en_proceso', 'resuelta')
            resuelto_por (str): Usuario que resuelve (opcional)
            notas (str): Notas de resolución (opcional)
            resuelto_por_username (str): Username del usuario (opcional)
            
        Returns:
            dict: Incidencia actualizada o None si falla
        """
        # ✅ USAR LOCK PARA THREAD-SAFETY
        with self._lock:
            try:
                # Validar estado
                if nuevo_estado not in ['pendiente', 'en_proceso', 'resuelta']:
                    logging.error(f"❌ Estado inválido: {nuevo_estado}")
                    return None
                
                if not self._ensure_connection():
                    return None
                
                # Obtener estado actual para comparar
                incidencia_actual = self.get_incidencia_por_id(incidencia_id)
                estado_anterior = incidencia_actual.get('estado', '') if incidencia_actual else ''
                
                # Construir query según el estado
                if nuevo_estado == 'resuelta':
                    query = """
                        UPDATE incidencias 
                        SET estado = %s, 
                            resuelto_por = %s,
                            notas_resolucion = %s,
                            fecha_resolucion = NOW()
                        WHERE id = %s
                    """
                    values = (nuevo_estado, resuelto_por, notas, incidencia_id)
                else:
                    query = """
                        UPDATE incidencias 
                        SET estado = %s
                        WHERE id = %s
                    """
                    values = (nuevo_estado, incidencia_id)
                
                with self.connection.cursor() as cursor:
                    cursor.execute(query, values)
                    self.connection.commit()
                    
                    if cursor.rowcount > 0:
                        logging.info(f"✅ Incidencia {incidencia_id} actualizada a estado '{nuevo_estado}'")
                        
                        # ✅ Registrar evento de cambio de estado en historial
                        import json
                        tipo_evento_map = {
                            'en_proceso': 'EN_PROCESO',
                            'resuelta': 'RESUELTA',
                            'pendiente': 'PENDIENTE'
                        }
                        tipo_evento = tipo_evento_map.get(nuevo_estado, nuevo_estado.upper())
                        
                        descripcion_map = {
                            'en_proceso': 'Incidencia tomada para resolver',
                            'resuelta': f'Incidencia resuelta{" - " + notas if notas else ""}',
                            'pendiente': 'Incidencia marcada como pendiente'
                        }
                        descripcion_evento = descripcion_map.get(nuevo_estado, f'Estado cambiado a {nuevo_estado}')
                        
                        datos_json = json.dumps({
                            'estado_anterior': estado_anterior,
                            'estado_nuevo': nuevo_estado,
                            'notas': notas
                        })
                        
                        # Usuario para el historial
                        usuario_historial = resuelto_por or 'Sistema'
                        username_historial = resuelto_por_username or 'sistema'
                        
                        query_historial = """
                            INSERT INTO historial_incidencias 
                            (incidencia_id, tipo_evento, descripcion, usuario, username, datos_adicionales)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """
                        cursor.execute(query_historial, (
                            incidencia_id, tipo_evento, descripcion_evento, 
                            usuario_historial, username_historial, datos_json
                        ))
                        self.connection.commit()
                        
                        return self.get_incidencia_por_id(incidencia_id)
                    else:
                        logging.warning(f"⚠️ No se encontró incidencia {incidencia_id}")
                        return None
                
            except Exception as e:
                logging.error(f"❌ Error actualizando incidencia {incidencia_id}: {e}")
                try:
                    self.connection.rollback()
                except:
                    pass
                return None
    
    def get_incidencias_activas_por_puesto(self) -> Dict:
        """
        Obtiene un diccionario con las incidencias activas por puesto
        Para mostrar el badge rojo en los puestos
        
        Returns:
            dict: {departamento: {puesto: cantidad}}
        """
        # ✅ USAR LOCK PARA THREAD-SAFETY
        with self._lock:
            try:
                if not self._ensure_connection():
                    return {}
                    
                query = """
                    SELECT 
                        departamento,
                        puesto,
                        COUNT(*) as cantidad
                    FROM incidencias
                    WHERE estado IN ('pendiente', 'en_proceso')
                    GROUP BY departamento, puesto
                """
                
                with self.connection.cursor() as cursor:
                    cursor.execute(query)
                    resultados = cursor.fetchall()
                
                # Convertir a formato esperado
                incidencias_por_puesto = {}
                
                for row in resultados:
                    dept = row['departamento']
                    puesto = row['puesto']
                    cantidad = row['cantidad']
                    
                    if dept not in incidencias_por_puesto:
                        incidencias_por_puesto[dept] = {}
                    
                    incidencias_por_puesto[dept][puesto] = cantidad
                
                logging.info(f"✅ Incidencias activas por puesto: {len(resultados)} puestos con incidencias")
                return incidencias_por_puesto
                
            except Exception as e:
                logging.error(f"❌ Error obteniendo incidencias activas: {e}")
                return {}
    
    # =========================================================================
    # MÉTODOS PARA COMENTARIOS
    # =========================================================================
    
    def agregar_comentario(self, incidencia_id: int, usuario: str, username: str, comentario: str) -> bool:
        """
        Agrega un comentario a una incidencia
        
        Args:
            incidencia_id (int): ID de la incidencia
            usuario (str): Nombre completo del usuario
            username (str): Username del usuario
            comentario (str): Texto del comentario
            
        Returns:
            bool: True si se agregó correctamente
        """
        # ✅ USAR LOCK PARA THREAD-SAFETY
        with self._lock:
            try:
                if not self._ensure_connection():
                    return False
                    
                query = """
                    INSERT INTO comentarios_incidencias 
                    (incidencia_id, usuario, username, comentario)
                    VALUES (%s, %s, %s, %s)
                """
                
                with self.connection.cursor() as cursor:
                    cursor.execute(query, (incidencia_id, usuario, username, comentario))
                    self.connection.commit()
                    
                    logging.info(f"✅ Comentario agregado a incidencia {incidencia_id}")
                    return True
                
            except Exception as e:
                logging.error(f"❌ Error agregando comentario: {e}")
                try:
                    self.connection.rollback()
                except:
                    pass
                return False
    
    def get_comentarios_incidencia(self, incidencia_id: int) -> List[Dict]:
        """
        Obtiene todos los comentarios de una incidencia
        
        Args:
            incidencia_id (int): ID de la incidencia
            
        Returns:
            list: Lista de comentarios
        """
        # ✅ USAR LOCK PARA THREAD-SAFETY
        with self._lock:
            try:
                if not self._ensure_connection():
                    return []
                    
                query = """
                    SELECT *
                    FROM comentarios_incidencias
                    WHERE incidencia_id = %s
                    ORDER BY fecha_comentario ASC
                """
                
                with self.connection.cursor() as cursor:
                    cursor.execute(query, (incidencia_id,))
                    comentarios = cursor.fetchall()
                
                # Convertir fechas a formato ISO
                for com in comentarios:
                    com['fecha_comentario'] = com['fecha_comentario'].isoformat() if com['fecha_comentario'] else None
                
                return comentarios
                
            except Exception as e:
                logging.error(f"❌ Error obteniendo comentarios: {e}")
                return []
    
    # =========================================================================
    # MÉTODOS PARA TIPOS DE INCIDENCIAS
    # =========================================================================
    
    def get_tipos_incidencias(self) -> List[Dict]:
        """
        Obtiene todos los tipos de incidencias activas
        
        Returns:
            list: Lista de tipos de incidencias
        """
        try:
            with self._lock:
                if not self._ensure_connection():
                    return []
                    
                query = """
                    SELECT codigo, descripcion, categoria, prioridad
                    FROM tipos_incidencias
                    WHERE activo = TRUE
                    ORDER BY categoria, descripcion
                """
                
                with self.connection.cursor() as cursor:
                    cursor.execute(query)
                    tipos = cursor.fetchall()
                
                logging.info(f"✅ Obtenidos {len(tipos)} tipos de incidencias")
                return tipos
            
        except Exception as e:
            logging.error(f"❌ Error obteniendo tipos de incidencias: {e}")
            return []
    
    # =========================================================================
    # MÉTODOS PARA ESTADÍSTICAS (ANALYTICS)
    # =========================================================================
    
    def get_estadisticas_generales(self, fecha_inicio: str = None, 
                                   fecha_fin: str = None,
                                   departamento: str = None) -> Dict:
        """
        Obtiene estadísticas generales del sistema con filtros
        """
        try:
            with self._lock:
                if not self._ensure_connection():
                    return {
                        'total_incidencias': 0,
                        'pendientes': 0,
                        'en_proceso': 0,
                        'resueltas': 0,
                        'tiempo_promedio_resolucion_horas': 0
                    }

                where_clauses = []
                params = []
                
                if fecha_inicio:
                    where_clauses.append("fecha_creacion >= %s")
                    params.append(fecha_inicio)
                if fecha_fin:
                    where_clauses.append("fecha_creacion <= %s")
                    params.append(fecha_fin + ' 23:59:59')
                if departamento and departamento != 'todos':
                    where_clauses.append("departamento = %s")
                    params.append(departamento)
                
                where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

                query = f"""
                    SELECT 
                        COUNT(*) as total_incidencias,
                        SUM(CASE WHEN estado = 'pendiente' THEN 1 ELSE 0 END) as pendientes,
                        SUM(CASE WHEN estado = 'en_proceso' THEN 1 ELSE 0 END) as en_proceso,
                        SUM(CASE WHEN estado = 'resuelta' THEN 1 ELSE 0 END) as resueltas,
                        AVG(CASE 
                            WHEN estado = 'resuelta' 
                            THEN TIMESTAMPDIFF(HOUR, fecha_creacion, fecha_resolucion) 
                            ELSE NULL 
                        END) as tiempo_promedio_resolucion_horas
                    FROM incidencias
                    {where_sql}
                """
                
                with self.connection.cursor() as cursor:
                    cursor.execute(query, tuple(params))
                    stats = cursor.fetchone()
                
                # Convertir valores None a 0
                if stats:
                    for key in stats:
                        if stats[key] is None:
                            stats[key] = 0
                    return stats
                
                return {
                    'total_incidencias': 0,
                    'pendientes': 0,
                    'en_proceso': 0,
                    'resueltas': 0,
                    'tiempo_promedio_resolucion_horas': 0
                }
            
        except Exception as e:
            logging.error(f"❌ Error obteniendo estadísticas: {e}")
            return {
                'total_incidencias': 0,
                'pendientes': 0,
                'en_proceso': 0,
                'resueltas': 0,
                'tiempo_promedio_resolucion_horas': 0
            }
    
    def get_incidencias_por_periodo(self, dias: int = 30,
                                   fecha_inicio: str = None,
                                   fecha_fin: str = None,
                                   departamento: str = None) -> Dict:
        """
        Obtiene incidencias agrupadas por día con filtros
        """
        try:
            with self._lock:
                if not self._ensure_connection():
                    return {'labels': [], 'data': []}

                where_clauses = []
                params = []
                
                if fecha_inicio:
                    where_clauses.append("fecha_creacion >= %s")
                    params.append(fecha_inicio)
                if fecha_fin:
                    where_clauses.append("fecha_creacion <= %s")
                    params.append(fecha_fin + ' 23:59:59')
                elif not fecha_inicio:
                    where_clauses.append("fecha_creacion >= DATE_SUB(NOW(), INTERVAL %s DAY)")
                    params.append(dias)
                
                if departamento and departamento != 'todos':
                    where_clauses.append("departamento = %s")
                    params.append(departamento)
                
                where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

                query = f"""
                    SELECT 
                        DATE(fecha_creacion) as fecha,
                        COUNT(*) as cantidad
                    FROM incidencias
                    {where_sql}
                    GROUP BY DATE(fecha_creacion)
                    ORDER BY fecha ASC
                """
                
                with self.connection.cursor() as cursor:
                    cursor.execute(query, tuple(params))
                    resultados = cursor.fetchall()
                
                labels = [row['fecha'].strftime('%d/%m') for row in resultados]
                data = [row['cantidad'] for row in resultados]
                
                return {'labels': labels, 'data': data}
            
        except Exception as e:
            logging.error(f"❌ Error obteniendo incidencias por periodo: {e}")
            return {'labels': [], 'data': []}
    
    def get_top_usuarios_reportan(self, limit: int = 10,
                                  fecha_inicio: str = None,
                                  fecha_fin: str = None,
                                  departamento: str = None) -> Dict:
        """
        Obtiene top usuarios que más reportan con filtros
        """
        try:
            with self._lock:
                if not self._ensure_connection():
                    return {'labels': [], 'data': []}

                where_clauses = []
                params = []
                
                if fecha_inicio:
                    where_clauses.append("fecha_creacion >= %s")
                    params.append(fecha_inicio)
                if fecha_fin:
                    where_clauses.append("fecha_creacion <= %s")
                    params.append(fecha_fin + ' 23:59:59')
                if departamento and departamento != 'todos':
                    where_clauses.append("departamento = %s")
                    params.append(departamento)
                
                where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

                query = f"""
                    SELECT 
                        reportado_por as usuario,
                        COUNT(*) as cantidad
                    FROM incidencias
                    {where_sql}
                    GROUP BY reportado_por
                    ORDER BY cantidad DESC
                    LIMIT %s
                """
                
                with self.connection.cursor() as cursor:
                    cursor.execute(query, tuple(params + [limit]))
                    resultados = cursor.fetchall()
                
                labels = [row['usuario'] for row in resultados]
                data = [row['cantidad'] for row in resultados]
                
                return {'labels': labels, 'data': data}
            
        except Exception as e:
            logging.error(f"❌ Error obteniendo top usuarios reportan: {e}")
            return {'labels': [], 'data': []}
    
    def get_top_usuarios_resuelven(self, limit: int = 10,
                                   fecha_inicio: str = None,
                                   fecha_fin: str = None,
                                   departamento: str = None) -> Dict:
        """
        Obtiene top usuarios que más resuelven con filtros
        """
        try:
            with self._lock:
                if not self._ensure_connection():
                    return {'labels': [], 'data': []}

                where_clauses = ["resuelto_por IS NOT NULL"]
                params = []
                
                if fecha_inicio:
                    where_clauses.append("fecha_creacion >= %s")
                    params.append(fecha_inicio)
                if fecha_fin:
                    where_clauses.append("fecha_creacion <= %s")
                    params.append(fecha_fin + ' 23:59:59')
                if departamento and departamento != 'todos':
                    where_clauses.append("departamento = %s")
                    params.append(departamento)
                
                where_sql = f"WHERE {' AND '.join(where_clauses)}"

                query = f"""
                    SELECT 
                        resuelto_por as usuario,
                        COUNT(*) as cantidad
                    FROM incidencias
                    {where_sql}
                    GROUP BY resuelto_por
                    ORDER BY cantidad DESC
                    LIMIT %s
                """
                
                with self.connection.cursor() as cursor:
                    cursor.execute(query, tuple(params + [limit]))
                    resultados = cursor.fetchall()
                
                labels = [row['usuario'] for row in resultados]
                data = [row['cantidad'] for row in resultados]
                
                return {'labels': labels, 'data': data}
            
        except Exception as e:
            logging.error(f"❌ Error obteniendo top usuarios resuelven: {e}")
            return {'labels': [], 'data': []}
    
    def get_distribucion_categorias(self) -> Dict:
        """
        Obtiene distribución por categoría
        
        Returns:
            dict: {labels: [...], data: [...]}
        """
        try:
            with self._lock:
                if not self._ensure_connection():
                    return {'labels': [], 'data': []}

                query = """
                    SELECT 
                        categoria,
                        COUNT(*) as cantidad
                    FROM incidencias
                    GROUP BY categoria
                    ORDER BY cantidad DESC
                """
                
                with self.connection.cursor() as cursor:
                    cursor.execute(query)
                    resultados = cursor.fetchall()
                
                labels = [row['categoria'] for row in resultados]
                data = [row['cantidad'] for row in resultados]
                
                return {'labels': labels, 'data': data}
            
        except Exception as e:
            logging.error(f"❌ Error obteniendo distribución categorías: {e}")
            return {'labels': [], 'data': []}
    
    def get_incidencias_por_departamento(self) -> Dict:
        """
        Obtiene incidencias por departamento
        
        Returns:
            dict: {labels: [...], data: [...]}
        """
        try:
            with self._lock:
                if not self._ensure_connection():
                    return {'labels': [], 'data': []}

                query = """
                    SELECT 
                        UPPER(departamento) as departamento,
                        COUNT(*) as cantidad
                    FROM incidencias
                    GROUP BY departamento
                    ORDER BY cantidad DESC
                """
                
                with self.connection.cursor() as cursor:
                    cursor.execute(query)
                    resultados = cursor.fetchall()
                
                labels = [row['departamento'] for row in resultados]
                data = [row['cantidad'] for row in resultados]
                
                return {'labels': labels, 'data': data}
            
        except Exception as e:
            logging.error(f"❌ Error obteniendo incidencias por departamento: {e}")
            return {'labels': [], 'data': []}
    
    def get_tiempo_promedio_resolucion_por_categoria(self, 
                                                    fecha_inicio: str = None,
                                                    fecha_fin: str = None,
                                                    departamento: str = None) -> Dict:
        """
        Obtiene tiempo promedio de resolución por categoría con filtros
        """
        try:
            with self._lock:
                if not self._ensure_connection():
                    return {'labels': [], 'data': []}

                where_clauses = ["estado = 'resuelta'", "fecha_resolucion IS NOT NULL"]
                params = []
                
                if fecha_inicio:
                    where_clauses.append("fecha_creacion >= %s")
                    params.append(fecha_inicio)
                if fecha_fin:
                    where_clauses.append("fecha_creacion <= %s")
                    params.append(fecha_fin + ' 23:59:59')
                if departamento and departamento != 'todos':
                    where_clauses.append("departamento = %s")
                    params.append(departamento)
                
                where_sql = f"WHERE {' AND '.join(where_clauses)}"

                query = f"""
                    SELECT 
                        categoria,
                        AVG(TIMESTAMPDIFF(HOUR, fecha_creacion, fecha_resolucion)) as promedio_horas
                    FROM incidencias
                    {where_sql}
                    GROUP BY categoria
                    ORDER BY promedio_horas DESC
                """
                
                with self.connection.cursor() as cursor:
                    cursor.execute(query, tuple(params))
                    resultados = cursor.fetchall()
                
                labels = [row['categoria'] for row in resultados]
                data = [round(float(row['promedio_horas']), 2) if row['promedio_horas'] else 0 for row in resultados]
                
                return {'labels': labels, 'data': data}
            
        except Exception as e:
            logging.error(f"❌ Error obteniendo tiempo promedio: {e}")
            return {'labels': [], 'data': []}
    
    def get_horas_pico(self, fecha_inicio: str = None,
                        fecha_fin: str = None,
                        departamento: str = None) -> Dict:
        """
        Obtiene horas del día con más incidencias con filtros
        """
        try:
            with self._lock:
                if not self._ensure_connection():
                    return {'labels': [], 'data': []}

                where_clauses = []
                params = []
                
                if fecha_inicio:
                    where_clauses.append("fecha_creacion >= %s")
                    params.append(fecha_inicio)
                if fecha_fin:
                    where_clauses.append("fecha_creacion <= %s")
                    params.append(fecha_fin + ' 23:59:59')
                if departamento and departamento != 'todos':
                    where_clauses.append("departamento = %s")
                    params.append(departamento)
                
                where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

                query = f"""
                    SELECT 
                        HOUR(fecha_creacion) as hora,
                        COUNT(*) as cantidad
                    FROM incidencias
                    {where_sql}
                    GROUP BY HOUR(fecha_creacion)
                    ORDER BY hora
                """
                
                with self.connection.cursor() as cursor:
                    cursor.execute(query, tuple(params))
                    resultados = cursor.fetchall()
                
                # Rellenar todas las horas (0-23)
                todas_horas = {h: 0 for h in range(24)}
                for row in resultados:
                    todas_horas[row['hora']] = row['cantidad']
                
                labels = [f"{h:02d}h" for h in range(24)]
                data = [todas_horas[h] for h in range(24)]
                
                return {'labels': labels, 'data': data}
            
        except Exception as e:
            logging.error(f"❌ Error obteniendo horas pico: {e}")
            return {'labels': [], 'data': []}
    
    def get_puestos_problematicos(self, limit: int = 15,
                                  fecha_inicio: str = None,
                                  fecha_fin: str = None,
                                  departamento: str = None) -> Dict:
        """
        Obtiene puestos con más incidencias con filtros
        """
        try:
            with self._lock:
                if not self._ensure_connection():
                    return {'labels': [], 'data': []}

                where_clauses = []
                params = []
                
                if fecha_inicio:
                    where_clauses.append("fecha_creacion >= %s")
                    params.append(fecha_inicio)
                if fecha_fin:
                    where_clauses.append("fecha_creacion <= %s")
                    params.append(fecha_fin + ' 23:59:59')
                if departamento and departamento != 'todos':
                    where_clauses.append("departamento = %s")
                    params.append(departamento)
                
                where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

                query = f"""
                    SELECT 
                        puesto,
                        COUNT(*) as cantidad
                    FROM incidencias
                    {where_sql}
                    GROUP BY puesto
                    ORDER BY cantidad DESC
                    LIMIT %s
                """
                
                with self.connection.cursor() as cursor:
                    cursor.execute(query, tuple(params + [limit]))
                    resultados = cursor.fetchall()
                
                labels = [str(row['puesto']) for row in resultados]
                data = [row['cantidad'] for row in resultados]
                
                return {'labels': labels, 'data': data}
            
        except Exception as e:
            logging.error(f"❌ Error obteniendo puestos problemáticos: {e}")
            return {'labels': [], 'data': []}

    # =========================================================================
    # MÉTODOS PARA ANALYTICS AVANZADO
    # =========================================================================
    
    def get_estadisticas_avanzadas(self, fecha_inicio: str = None, fecha_fin: str = None, 
                                    departamento: str = None) -> Dict:
        """
        Obtiene estadísticas avanzadas con filtros
        
        Args:
            fecha_inicio (str): Fecha inicio en formato YYYY-MM-DD
            fecha_fin (str): Fecha fin en formato YYYY-MM-DD
            departamento (str): Filtrar por departamento
            
        Returns:
            dict: Estadísticas completas
        """
        with self._lock:  # ✅ USAR LOCK PARA THREAD-SAFETY
            if not self._ensure_connection():
                return {}
            
            try:
                # Construir WHERE dinámico
                where_clauses = []
                params = []
                
                if fecha_inicio:
                    where_clauses.append("fecha_creacion >= %s")
                    params.append(fecha_inicio)
                if fecha_fin:
                    where_clauses.append("fecha_creacion <= %s")
                    params.append(fecha_fin + ' 23:59:59')
                if departamento and departamento != 'todos':
                    where_clauses.append("departamento = %s")
                    params.append(departamento)
                
                where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
                
                # Estadísticas generales
                # Estadísticas generales
                query = f"""
                    SELECT 
                        COUNT(*) as total,
                        SUM(CASE WHEN estado = 'pendiente' THEN 1 ELSE 0 END) as pendientes,
                        SUM(CASE WHEN estado = 'en_proceso' THEN 1 ELSE 0 END) as en_proceso,
                        SUM(CASE WHEN estado = 'pausada' THEN 1 ELSE 0 END) as pausadas,
                        SUM(CASE WHEN estado = 'resuelta' THEN 1 ELSE 0 END) as resueltas,
                        AVG(CASE WHEN estado = 'resuelta' 
                            THEN TIMESTAMPDIFF(MINUTE, fecha_creacion, fecha_resolucion) 
                            ELSE NULL END) as promedio_minutos_total,
                        AVG(CASE WHEN estado = 'resuelta' 
                            THEN TIMESTAMPDIFF(MINUTE, fecha_creacion, fecha_resolucion) - COALESCE(tiempo_pausado_minutos, 0)
                            ELSE NULL END) as promedio_minutos_efectivo,
                        SUM(COALESCE(tiempo_pausado_minutos, 0)) as total_tiempo_pausado
                    FROM incidencias
                    {where_sql}
                """
                
                with self.connection.cursor() as cursor:
                    cursor.execute(query, tuple(params))
                    stats = cursor.fetchone()
                
                return {
                    'total': stats['total'] or 0,
                    'pendientes': stats['pendientes'] or 0,
                    'en_proceso': stats['en_proceso'] or 0,
                    'pausadas': stats['pausadas'] or 0,
                    'resueltas': stats['resueltas'] or 0,
                    'promedio_minutos_total': round(float(stats['promedio_minutos_total'] or 0), 1),
                    'promedio_minutos_efectivo': round(float(stats['promedio_minutos_efectivo'] or 0), 1),
                    'total_tiempo_pausado': stats['total_tiempo_pausado'] or 0,
                    'ratio_resolucion': round((stats['resueltas'] or 0) / max(stats['total'] or 1, 1) * 100, 1),
                    'ratio_pausadas': round((stats['pausadas'] or 0) / max(stats['total'] or 1, 1) * 100, 1)
                }
                
            except Exception as e:
                logging.error(f"❌ Error obteniendo estadísticas avanzadas: {e}")
                return {}
    
    def get_sla_compliance(self, sla_horas: int = 4, fecha_inicio: str = None, 
                           fecha_fin: str = None) -> Dict:
        """
        Calcula cumplimiento de SLA
        
        Args:
            sla_horas (int): Objetivo de horas para resolver
            fecha_inicio (str): Filtro fecha inicio
            fecha_fin (str): Filtro fecha fin
            
        Returns:
            dict: Estadísticas de SLA
        """
        with self._lock:  # ✅ USAR LOCK PARA THREAD-SAFETY
            if not self._ensure_connection():
                return {}
            
            try:
                where_clauses = ["estado = 'resuelta'"]
                params = [sla_horas * 60]  # Convertir a minutos
                
                if fecha_inicio:
                    where_clauses.append("fecha_creacion >= %s")
                    params.append(fecha_inicio)
                if fecha_fin:
                    where_clauses.append("fecha_creacion <= %s")
                    params.append(fecha_fin + ' 23:59:59')
                
                where_sql = f"WHERE {' AND '.join(where_clauses)}"
                
                query = f"""
                    SELECT 
                        COUNT(*) as total_resueltas,
                        SUM(CASE 
                            WHEN (TIMESTAMPDIFF(MINUTE, fecha_creacion, fecha_resolucion) - COALESCE(tiempo_pausado_minutos, 0)) <= %s 
                            THEN 1 ELSE 0 
                        END) as dentro_sla,
                        SUM(CASE 
                            WHEN (TIMESTAMPDIFF(MINUTE, fecha_creacion, fecha_resolucion) - COALESCE(tiempo_pausado_minutos, 0)) > %s 
                            THEN 1 ELSE 0 
                        END) as fuera_sla
                    FROM incidencias
                    {where_sql}
                """
                
                # Añadir el parámetro de SLA dos veces para las dos comparaciones
                # Añadir el parámetro de SLA dos veces para las dos comparaciones
                params.insert(1, sla_horas * 60)
                
                with self.connection.cursor() as cursor:
                    cursor.execute(query, tuple(params))
                    result = cursor.fetchone()
                
                total = result['total_resueltas'] or 0
                dentro = result['dentro_sla'] or 0
                fuera = result['fuera_sla'] or 0
                
                return {
                    'sla_objetivo_horas': sla_horas,
                    'total_resueltas': total,
                    'dentro_sla': dentro,
                    'fuera_sla': fuera,
                    'porcentaje_cumplimiento': round(dentro / max(total, 1) * 100, 1),
                    'status': 'excelente' if (dentro / max(total, 1) * 100) >= 90 else 
                             'bueno' if (dentro / max(total, 1) * 100) >= 75 else
                             'mejorable' if (dentro / max(total, 1) * 100) >= 50 else 'crítico'
                }
                
            except Exception as e:
                logging.error(f"❌ Error calculando SLA: {e}")
                return {}
    
    def get_tiempos_por_motivo_pausa(self, fecha_inicio: str = None, fecha_fin: str = None) -> Dict:
        """
        Obtiene tiempos agrupados por motivo de pausa
        """
        with self._lock:  # ✅ USAR LOCK PARA THREAD-SAFETY
            if not self._ensure_connection():
                return {'labels': [], 'data': [], 'colores': []}
            
            try:
                where_clauses = ["fecha_fin_pausa IS NOT NULL"]
                params = []
                
                if fecha_inicio:
                    where_clauses.append("fecha_inicio_pausa >= %s")
                    params.append(fecha_inicio)
                if fecha_fin:
                    where_clauses.append("fecha_inicio_pausa <= %s")
                    params.append(fecha_fin + ' 23:59:59')
                
                where_sql = f"WHERE {' AND '.join(where_clauses)}"
                
                query = f"""
                    SELECT 
                        motivo_descripcion,
                        COUNT(*) as cantidad,
                        SUM(duracion_minutos) as total_minutos,
                        AVG(duracion_minutos) as promedio_minutos
                    FROM historial_pausas
                    {where_sql}
                    GROUP BY motivo_descripcion
                    ORDER BY total_minutos DESC
                """
                
                with self.connection.cursor() as cursor:
                    cursor.execute(query, tuple(params))
                    resultados = cursor.fetchall()
                
                labels = [r['motivo_descripcion'] for r in resultados]
                data = [r['total_minutos'] or 0 for r in resultados]
                
                # Colores para cada motivo
                colores = [
                    'rgba(159, 122, 234, 0.8)',  # Morado
                    'rgba(237, 137, 54, 0.8)',   # Naranja
                    'rgba(66, 153, 225, 0.8)',   # Azul
                    'rgba(72, 187, 120, 0.8)',   # Verde
                    'rgba(252, 129, 129, 0.8)',  # Rojo
                    'rgba(160, 174, 192, 0.8)',  # Gris
                ]
                
                return {
                    'labels': labels,
                    'data': data,
                    'colores': colores[:len(labels)],
                    'detalles': resultados
                }
                
            except Exception as e:
                logging.error(f"❌ Error obteniendo tiempos por motivo: {e}")
                return {'labels': [], 'data': [], 'colores': []}
    
    def get_tiempos_efectivo_vs_total(self, dias: int = 30, fecha_inicio: str = None,
                                       fecha_fin: str = None) -> Dict:
        """
        Compara tiempo efectivo vs tiempo total por día
        
        Args:
            dias (int): Número de días hacia atrás (usado si no hay fechas)
            fecha_inicio (str): Fecha inicio en formato YYYY-MM-DD
            fecha_fin (str): Fecha fin en formato YYYY-MM-DD
        """
        with self._lock:  # ✅ USAR LOCK PARA THREAD-SAFETY
            if not self._ensure_connection():
                return {'labels': [], 'efectivo': [], 'pausado': []}
            
            try:
                # ✅ CONSTRUIR WHERE DINÁMICO
                where_clauses = ["estado = 'resuelta'"]
                params = []
                
                if fecha_inicio and fecha_fin:
                    # Usar filtros de fecha específicos
                    where_clauses.append("fecha_creacion >= %s")
                    params.append(fecha_inicio)
                    where_clauses.append("fecha_creacion <= %s")
                    params.append(fecha_fin + ' 23:59:59')
                else:
                    # Usar días hacia atrás
                    where_clauses.append("fecha_creacion >= DATE_SUB(CURDATE(), INTERVAL %s DAY)")
                    params.append(dias)
                
                where_sql = " AND ".join(where_clauses)
                
                query = f"""
                    SELECT 
                        DATE(fecha_creacion) as fecha,
                        AVG(TIMESTAMPDIFF(MINUTE, fecha_creacion, COALESCE(fecha_resolucion, NOW()))) as promedio_total,
                        AVG(TIMESTAMPDIFF(MINUTE, fecha_creacion, COALESCE(fecha_resolucion, NOW())) 
                            - COALESCE(tiempo_pausado_minutos, 0)) as promedio_efectivo,
                        AVG(COALESCE(tiempo_pausado_minutos, 0)) as promedio_pausado
                    FROM incidencias
                    WHERE {where_sql}
                    GROUP BY DATE(fecha_creacion)
                    ORDER BY fecha
                """
                
                with self.connection.cursor() as cursor:
                    cursor.execute(query, tuple(params))
                    resultados = cursor.fetchall()
                
                labels = [r['fecha'].strftime('%d/%m') for r in resultados]
                efectivo = [round(float(r['promedio_efectivo'] or 0), 1) for r in resultados]
                pausado = [round(float(r['promedio_pausado'] or 0), 1) for r in resultados]
                
                return {
                    'labels': labels,
                    'efectivo': efectivo,
                    'pausado': pausado
                }
                
            except Exception as e:
                logging.error(f"❌ Error obteniendo tiempos efectivo vs total: {e}")
                return {'labels': [], 'efectivo': [], 'pausado': []}
    
    def get_eficiencia_tecnicos(self, fecha_inicio: str = None, fecha_fin: str = None) -> List[Dict]:
        """
        Obtiene eficiencia por técnico IT
        """
        with self._lock:  # ✅ USAR LOCK PARA THREAD-SAFETY
            if not self._ensure_connection():
                return []
            
            try:
                where_clauses = ["estado = 'resuelta'", "resuelto_por IS NOT NULL"]
                params = []
                
                if fecha_inicio:
                    where_clauses.append("fecha_resolucion >= %s")
                    params.append(fecha_inicio)
                if fecha_fin:
                    where_clauses.append("fecha_resolucion <= %s")
                    params.append(fecha_fin + ' 23:59:59')
                
                where_sql = f"WHERE {' AND '.join(where_clauses)}"
                
                query = f"""
                    SELECT 
                        resuelto_por as tecnico,
                        COUNT(*) as total_resueltas,
                        AVG(TIMESTAMPDIFF(MINUTE, fecha_creacion, fecha_resolucion) 
                            - COALESCE(tiempo_pausado_minutos, 0)) as promedio_efectivo,
                        SUM(COALESCE(tiempo_pausado_minutos, 0)) as total_pausado
                    FROM incidencias
                    {where_sql}
                    GROUP BY resuelto_por
                    ORDER BY total_resueltas DESC
                """
                
                with self.connection.cursor() as cursor:
                    cursor.execute(query, tuple(params))
                    resultados = cursor.fetchall()
                
                return [{
                    'tecnico': r['tecnico'],
                    'total_resueltas': r['total_resueltas'],
                    'promedio_efectivo': round(float(r['promedio_efectivo'] or 0), 1),
                    'total_pausado': r['total_pausado'] or 0
                } for r in resultados]
                
            except Exception as e:
                logging.error(f"❌ Error obteniendo eficiencia de técnicos: {e}")
                return []
    
    def exportar_incidencias_csv(self, fecha_inicio: str = None, fecha_fin: str = None,
                                  departamento: str = None) -> List[Dict]:
        """
        Exporta incidencias para CSV/Excel
        """
        if not self._ensure_connection():
            return []
        
        try:
            where_clauses = []
            params = []
            
            if fecha_inicio:
                where_clauses.append("fecha_creacion >= %s")
                params.append(fecha_inicio)
            if fecha_fin:
                where_clauses.append("fecha_creacion <= %s")
                params.append(fecha_fin + ' 23:59:59')
            if departamento and departamento != 'todos':
                where_clauses.append("departamento = %s")
                params.append(departamento)
            
            where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
            
            query = f"""
                SELECT 
                    id,
                    departamento,
                    puesto,
                    categoria,
                    descripcion,
                    prioridad,
                    estado,
                    reportado_por,
                    resuelto_por,
                    fecha_creacion,
                    fecha_resolucion,
                    TIMESTAMPDIFF(MINUTE, fecha_creacion, COALESCE(fecha_resolucion, NOW())) as minutos_total,
                    COALESCE(tiempo_pausado_minutos, 0) as minutos_pausado,
                    TIMESTAMPDIFF(MINUTE, fecha_creacion, COALESCE(fecha_resolucion, NOW())) 
                        - COALESCE(tiempo_pausado_minutos, 0) as minutos_efectivo,
                    notas_resolucion
                FROM incidencias
                {where_sql}
                ORDER BY fecha_creacion DESC
            """
            
            with self._lock:
                if not self._ensure_connection():
                    return []
                with self.connection.cursor() as cursor:
                    cursor.execute(query, tuple(params))
                    resultados = cursor.fetchall()
            
            # Convertir fechas a string
            for r in resultados:
                if r['fecha_creacion']:
                    r['fecha_creacion'] = r['fecha_creacion'].strftime('%Y-%m-%d %H:%M:%S')
                if r['fecha_resolucion']:
                    r['fecha_resolucion'] = r['fecha_resolucion'].strftime('%Y-%m-%d %H:%M:%S')
            
            return resultados
            
        except Exception as e:
            logging.error(f"❌ Error exportando incidencias: {e}")
            return []

    # =========================================================================
    # MÉTODOS PARA SISTEMA DE PAUSAS
    # =========================================================================
    
    def get_motivos_pausa(self, activos_solo: bool = True) -> List[Dict]:
        """
        Obtiene la lista de motivos de pausa disponibles
        
        Args:
            activos_solo (bool): Si True, solo devuelve motivos activos
            
        Returns:
            list: Lista de motivos de pausa
        """
        if not self._ensure_connection():
            return []
        
        try:
            with self._lock:  # ✅ USAR LOCK
                query = """
                    SELECT id, codigo, descripcion, requiere_descripcion, activo, orden
                    FROM motivos_pausa
                """
                if activos_solo:
                    query += " WHERE activo = TRUE"
                query += " ORDER BY orden, descripcion"
                
                with self.connection.cursor() as cursor:
                    cursor.execute(query)
                    return cursor.fetchall()
            
        except Exception as e:
            logging.error(f"❌ Error obteniendo motivos de pausa: {e}")
            return []
    
    def crear_motivo_pausa(self, codigo: str, descripcion: str, 
                           requiere_descripcion: bool = False, orden: int = 50) -> bool:
        """
        Crea un nuevo motivo de pausa
        
        Args:
            codigo (str): Código único del motivo
            descripcion (str): Descripción del motivo
            requiere_descripcion (bool): Si requiere descripción adicional
            orden (int): Orden de aparición
            
        Returns:
            bool: True si se creó correctamente
        """
        if not self._ensure_connection():
            return False
        
        try:
            with self._lock:  # ✅ USAR LOCK
                query = """
                    INSERT INTO motivos_pausa (codigo, descripcion, requiere_descripcion, orden)
                    VALUES (%s, %s, %s, %s)
                """
                with self.connection.cursor() as cursor:
                    cursor.execute(query, (codigo.upper(), descripcion, requiere_descripcion, orden))
                    self.connection.commit()
                logging.info(f"✅ Motivo de pausa creado: {codigo}")
                return True
            
        except Exception as e:
            logging.error(f"❌ Error creando motivo de pausa: {e}")
            self.connection.rollback()
            return False
    
    def actualizar_motivo_pausa(self, codigo: str, descripcion: str = None, 
                                 activo: bool = None, orden: int = None) -> bool:
        """
        Actualiza un motivo de pausa existente
        """
        if not self._ensure_connection():
            return False
        
        try:
            with self._lock:  # ✅ USAR LOCK
                updates = []
                params = []
                
                if descripcion is not None:
                    updates.append("descripcion = %s")
                    params.append(descripcion)
                if activo is not None:
                    updates.append("activo = %s")
                    params.append(activo)
                if orden is not None:
                    updates.append("orden = %s")
                    params.append(orden)
                
                if not updates:
                    return False
                
                params.append(codigo.upper())
                query = f"UPDATE motivos_pausa SET {', '.join(updates)} WHERE codigo = %s"
                
                with self.connection.cursor() as cursor:
                    cursor.execute(query, tuple(params))
                    self.connection.commit()
                    rows = cursor.rowcount
                
                if rows > 0:
                    logging.info(f"✅ Motivo de pausa actualizado: {codigo}")
                    return True
                return False
            
        except Exception as e:
            logging.error(f"❌ Error actualizando motivo de pausa: {e}")
            self.connection.rollback()
            return False
    
    def pausar_incidencia(self, incidencia_id: int, motivo_codigo: str, 
                          usuario: str, username: str, 
                          descripcion_adicional: str = None) -> Optional[Dict]:
        """
        Pausa una incidencia
        
        Args:
            incidencia_id (int): ID de la incidencia
            motivo_codigo (str): Código del motivo de pausa
            usuario (str): Nombre completo del usuario
            username (str): Username del usuario
            descripcion_adicional (str): Descripción adicional opcional
            
        Returns:
            dict: Incidencia actualizada o None si falla
        """
        if not self._ensure_connection():
            return None
        
        try:
            with self._lock:  # ✅ USAR LOCK
                # Verificar que la incidencia existe y está en_proceso
                incidencia = self.get_incidencia_por_id(incidencia_id)
                if not incidencia:
                    logging.error(f"❌ Incidencia {incidencia_id} no encontrada")
                    return None
                
                if incidencia['estado'] not in ['en_proceso', 'pendiente']:
                    logging.error(f"❌ Incidencia {incidencia_id} no se puede pausar (estado: {incidencia['estado']})")
                    return None
                
                with self.connection.cursor() as cursor:
                    # Obtener descripción del motivo
                    cursor.execute(
                        "SELECT descripcion FROM motivos_pausa WHERE codigo = %s",
                        (motivo_codigo.upper(),)
                    )
                    motivo = cursor.fetchone()
                    if not motivo:
                        logging.error(f"❌ Motivo de pausa no encontrado: {motivo_codigo}")
                        return None
                    
                    motivo_descripcion = motivo['descripcion']
                    
                    # Actualizar incidencia a pausada
                    query_update = """
                        UPDATE incidencias 
                        SET estado = 'pausada',
                            motivo_pausa_actual = %s,
                            fecha_ultima_pausa = NOW()
                        WHERE id = %s
                    """
                    cursor.execute(query_update, (motivo_codigo.upper(), incidencia_id))
                    
                    # Registrar en historial de pausas
                    query_pausa = """
                        INSERT INTO historial_pausas 
                        (incidencia_id, motivo_codigo, motivo_descripcion, descripcion_adicional,
                         pausado_por, pausado_por_username, fecha_inicio_pausa)
                        VALUES (%s, %s, %s, %s, %s, %s, NOW())
                    """
                    cursor.execute(query_pausa, (
                        incidencia_id, motivo_codigo.upper(), motivo_descripcion,
                        descripcion_adicional, usuario, username
                    ))
                    
                    # Registrar en historial de incidencias (timeline)
                    query_historial = """
                        INSERT INTO historial_incidencias 
                        (incidencia_id, tipo_evento, descripcion, usuario, username, datos_adicionales)
                        VALUES (%s, 'PAUSADA', %s, %s, %s, %s)
                    """
                    descripcion_evento = f"Incidencia pausada: {motivo_descripcion}"
                    if descripcion_adicional:
                        descripcion_evento += f" - {descripcion_adicional}"
                    
                    import json
                    datos_json = json.dumps({
                        'motivo_codigo': motivo_codigo.upper(),
                        'motivo_descripcion': motivo_descripcion,
                        'descripcion_adicional': descripcion_adicional
                    })
                    
                    cursor.execute(query_historial, (
                        incidencia_id, descripcion_evento, usuario, username, datos_json
                    ))
                    
                    self.connection.commit()
                
                logging.info(f"⏸️ Incidencia {incidencia_id} pausada por {username}: {motivo_descripcion}")
                
                return self.get_incidencia_por_id(incidencia_id)
            
        except Exception as e:
            logging.error(f"❌ Error pausando incidencia {incidencia_id}: {e}")
            self.connection.rollback()
            return None
    
    def reanudar_incidencia(self, incidencia_id: int, usuario: str, 
                            username: str, notas: str = None) -> Optional[Dict]:
        """
        Reanuda una incidencia pausada
        
        Args:
            incidencia_id (int): ID de la incidencia
            usuario (str): Nombre completo del usuario
            username (str): Username del usuario
            notas (str): Notas al reanudar (opcional)
            
        Returns:
            dict: Incidencia actualizada o None si falla
        """
        if not self._ensure_connection():
            return None
        
        try:
            with self._lock:  # ✅ USAR LOCK
                # Verificar que la incidencia está pausada
                incidencia = self.get_incidencia_por_id(incidencia_id)
                if not incidencia:
                    logging.error(f"❌ Incidencia {incidencia_id} no encontrada")
                    return None
                
                if incidencia['estado'] != 'pausada':
                    logging.error(f"❌ Incidencia {incidencia_id} no está pausada (estado: {incidencia['estado']})")
                    return None
                
                with self.connection.cursor() as cursor:
                    # Calcular duración de la pausa actual
                    query_duracion = """
                        SELECT id, fecha_inicio_pausa, motivo_descripcion
                        FROM historial_pausas 
                        WHERE incidencia_id = %s AND fecha_fin_pausa IS NULL
                        ORDER BY fecha_inicio_pausa DESC
                        LIMIT 1
                    """
                    cursor.execute(query_duracion, (incidencia_id,))
                    pausa_activa = cursor.fetchone()
                    
                    duracion_minutos = 0
                    if pausa_activa:
                        # Actualizar la pausa con la fecha de fin y duración
                        query_cerrar_pausa = """
                            UPDATE historial_pausas 
                            SET fecha_fin_pausa = NOW(),
                                duracion_minutos = TIMESTAMPDIFF(MINUTE, fecha_inicio_pausa, NOW()),
                                reanudado_por = %s,
                                reanudado_por_username = %s,
                                notas_reanudacion = %s
                            WHERE id = %s
                        """
                        cursor.execute(query_cerrar_pausa, (
                            usuario, username, notas, pausa_activa['id']
                        ))
                        
                        # Obtener la duración calculada
                        cursor.execute(
                            "SELECT duracion_minutos FROM historial_pausas WHERE id = %s",
                            (pausa_activa['id'],)
                        )
                        result = cursor.fetchone()
                        duracion_minutos = result['duracion_minutos'] if result else 0
                    
                    # Actualizar tiempo total pausado en la incidencia
                    query_update = """
                        UPDATE incidencias 
                        SET estado = 'en_proceso',
                            motivo_pausa_actual = NULL,
                            tiempo_pausado_minutos = tiempo_pausado_minutos + %s
                        WHERE id = %s
                    """
                    cursor.execute(query_update, (duracion_minutos, incidencia_id))
                    
                    # Registrar en historial de incidencias (timeline)
                    import json
                    descripcion_evento = f"Incidencia reanudada (pausada {duracion_minutos} min)"
                    if notas:
                        descripcion_evento += f" - {notas}"
                    
                    datos_json = json.dumps({
                        'duracion_pausa_minutos': duracion_minutos,
                        'notas': notas
                    })
                    
                    query_historial = """
                        INSERT INTO historial_incidencias 
                        (incidencia_id, tipo_evento, descripcion, usuario, username, datos_adicionales)
                        VALUES (%s, 'REANUDADA', %s, %s, %s, %s)
                    """
                    cursor.execute(query_historial, (
                        incidencia_id, descripcion_evento, usuario, username, datos_json
                    ))
                    
                    self.connection.commit()
                
                logging.info(f"▶️ Incidencia {incidencia_id} reanudada por {username} (pausada {duracion_minutos} min)")
                
                return self.get_incidencia_por_id(incidencia_id)
            
        except Exception as e:
            logging.error(f"❌ Error reanudando incidencia {incidencia_id}: {e}")
            self.connection.rollback()
            return None
    
    def get_historial_pausas(self, incidencia_id: int) -> List[Dict]:
        """
        Obtiene el historial de pausas de una incidencia
        
        Args:
            incidencia_id (int): ID de la incidencia
            
        Returns:
            list: Lista de pausas
        """
        if not self._ensure_connection():
            return []
        
        try:
            with self._lock:  # ✅ USAR LOCK
                query = """
                    SELECT 
                        id, motivo_codigo, motivo_descripcion, descripcion_adicional,
                        pausado_por, pausado_por_username,
                        fecha_inicio_pausa, fecha_fin_pausa, duracion_minutos,
                        reanudado_por, reanudado_por_username, notas_reanudacion
                    FROM historial_pausas
                    WHERE incidencia_id = %s
                    ORDER BY fecha_inicio_pausa DESC
                """
                
                with self.connection.cursor() as cursor:
                    cursor.execute(query, (incidencia_id,))
                    pausas = cursor.fetchall()
                
                # Convertir fechas a ISO
                for pausa in pausas:
                    pausa['fecha_inicio_pausa'] = pausa['fecha_inicio_pausa'].isoformat() if pausa['fecha_inicio_pausa'] else None
                    pausa['fecha_fin_pausa'] = pausa['fecha_fin_pausa'].isoformat() if pausa['fecha_fin_pausa'] else None
                    pausa['activa'] = pausa['fecha_fin_pausa'] is None
                
                return pausas
            
        except Exception as e:
            logging.error(f"❌ Error obteniendo historial de pausas: {e}")
            return []
    
    def get_timeline_incidencia(self, incidencia_id: int) -> List[Dict]:
        """
        Obtiene la línea temporal completa de una incidencia
        
        Args:
            incidencia_id (int): ID de la incidencia
            
        Returns:
            list: Lista de eventos ordenados cronológicamente
        """
        if not self._ensure_connection():
            return []
        
        try:
            with self._lock:  # ✅ USAR LOCK
                query = """
                    SELECT 
                        id, tipo_evento, descripcion, datos_adicionales,
                        usuario, username, fecha_evento
                    FROM historial_incidencias
                    WHERE incidencia_id = %s
                    ORDER BY fecha_evento ASC
                """
                
                with self.connection.cursor() as cursor:
                    cursor.execute(query, (incidencia_id,))
                    eventos = cursor.fetchall()
                
                import json
                for evento in eventos:
                    evento['fecha_evento'] = evento['fecha_evento'].isoformat() if evento['fecha_evento'] else None
                    # Parsear JSON si existe
                    if evento['datos_adicionales']:
                        try:
                            evento['datos_adicionales'] = json.loads(evento['datos_adicionales'])
                        except:
                            evento['datos_adicionales'] = {}
                
                return eventos
            
        except Exception as e:
            logging.error(f"❌ Error obteniendo timeline: {e}")
            return []
    
    def registrar_evento_historial(self, incidencia_id: int, tipo_evento: str,
                                    descripcion: str, usuario: str, 
                                    username: str, datos_adicionales: dict = None) -> bool:
        """
        Registra un evento en el historial de la incidencia
        
        Args:
            incidencia_id (int): ID de la incidencia
            tipo_evento (str): CREADA, EN_PROCESO, PAUSADA, REANUDADA, RESUELTA, COMENTARIO, EDITADA
            descripcion (str): Descripción del evento
            usuario (str): Nombre completo
            username (str): Username
            datos_adicionales (dict): Datos extra en formato dict
            
        Returns:
            bool: True si se registró correctamente
        """
        if not self._ensure_connection():
            return False
        
        try:
            with self._lock:  # ✅ USAR LOCK
                import json
                datos_json = json.dumps(datos_adicionales) if datos_adicionales else None
                
                query = """
                    INSERT INTO historial_incidencias 
                    (incidencia_id, tipo_evento, descripcion, usuario, username, datos_adicionales)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """
                with self.connection.cursor() as cursor:
                    cursor.execute(query, (
                        incidencia_id, tipo_evento, descripcion, usuario, username, datos_json
                    ))
                    self.connection.commit()
                return True
            
        except Exception as e:
            logging.error(f"❌ Error registrando evento en historial: {e}")
            self.connection.rollback()
            return False
    
    def get_estadisticas_pausas(self) -> Dict:
        """
        Obtiene estadísticas de pausas del sistema
        
        Returns:
            dict: Estadísticas de pausas
        """
        if not self._ensure_connection():
            return {}
        
        try:
            with self._lock:  # ✅ USAR LOCK
                query = """
                    SELECT 
                        COUNT(*) as total_pausas,
                        COUNT(DISTINCT incidencia_id) as incidencias_pausadas,
                        AVG(duracion_minutos) as promedio_duracion_minutos,
                        SUM(duracion_minutos) as total_minutos_pausados
                    FROM historial_pausas
                    WHERE fecha_fin_pausa IS NOT NULL
                """
                
                with self.connection.cursor() as cursor:
                    cursor.execute(query)
                    stats = cursor.fetchone()
                    
                    # Pausas por motivo
                    query_motivos = """
                        SELECT 
                            motivo_descripcion,
                            COUNT(*) as cantidad,
                            AVG(duracion_minutos) as promedio_minutos
                        FROM historial_pausas
                        WHERE fecha_fin_pausa IS NOT NULL
                        GROUP BY motivo_descripcion
                        ORDER BY cantidad DESC
                    """
                    cursor.execute(query_motivos)
                    por_motivo = cursor.fetchall()
                
                return {
                    'total_pausas': stats['total_pausas'] or 0,
                    'incidencias_pausadas': stats['incidencias_pausadas'] or 0,
                    'promedio_duracion_minutos': round(float(stats['promedio_duracion_minutos'] or 0), 2),
                    'total_minutos_pausados': stats['total_minutos_pausados'] or 0,
                    'por_motivo': por_motivo
                }
            
        except Exception as e:
            logging.error(f"❌ Error obteniendo estadísticas de pausas: {e}")
            return {}

# =========================================================================
    # MÉTODOS PARA GESTIÓN DE USUARIOS
    # =========================================================================
    
    def verificar_credenciales(self, username: str, password: str) -> Optional[Dict]:
        """
        Verifica credenciales de usuario con soporte para hash de contraseñas.
        Migra automáticamente contraseñas en texto plano a hash.
        
        Args:
            username (str): Nombre de usuario
            password (str): Contraseña
            
        Returns:
            dict: Datos del usuario si las credenciales son correctas, None si no
        """
        # Asegurar conexión activa - CRÍTICO para el login
        if not self._ensure_connection():
            logging.error("❌ No hay conexión MySQL disponible para login")
            return None
        
        with self._lock:
            try:
                # Importar módulo de seguridad
                try:
                    from security import hash_password, verify_password, is_password_hashed, migrate_password_if_needed
                    use_hash = True
                except ImportError:
                    use_hash = False
                    logging.warning("⚠️ Módulo security no disponible, usando contraseñas sin hash")
                
                # Obtener usuario por username
                query = """
                    SELECT id, username, password, nombre_completo, rol, departamento, activo
                    FROM usuarios
                    WHERE username = %s AND activo = TRUE
                """
                
                with self.connection.cursor() as cursor:
                    cursor.execute(query, (username,))
                    usuario = cursor.fetchone()
            
                if not usuario:
                    logging.warning(f"❌ Login fallido: usuario {username} no encontrado")
                    return None
                
                stored_password = usuario['password']
                password_valid = False
                
                if use_hash:
                    # Verificar si la contraseña almacenada está hasheada
                    if is_password_hashed(stored_password):
                        # Usar verify_password para comparación segura
                        password_valid = verify_password(password, stored_password)
                    else:
                        # Contraseña en texto plano - verificar y migrar
                        if stored_password == password:
                            password_valid = True
                            # Migrar a hash
                            new_hash = hash_password(password)
                            self._update_password_hash(usuario['id'], new_hash)
                            logging.info(f"🔐 Contraseña migrada a hash para: {username}")
                else:
                    # Sin hash, comparación directa
                    password_valid = (stored_password == password)
                
                if password_valid:
                    logging.info(f"✅ Login exitoso: {username} ({usuario['rol']})")
                    # No devolver la contraseña
                    return {
                        'username': usuario['username'],
                        'nombre_completo': usuario['nombre_completo'],
                        'rol': usuario['rol'],
                        'departamento': usuario['departamento'],
                        'activo': usuario['activo']
                    }
                else:
                    logging.warning(f"❌ Login fallido: contraseña incorrecta para {username}")
                    return None
                    
            except Exception as e:
                logging.error(f"❌ Error verificando credenciales: {e}")
                import traceback
                logging.error(traceback.format_exc())
                return None
    
    def _update_password_hash(self, user_id: int, password_hash: str) -> bool:
        """
        Actualiza la contraseña de un usuario con su hash.
        Usado internamente para migración automática.
        """
        with self._lock:
            try:
                if not self._ensure_connection():
                    return False
                    
                query = "UPDATE usuarios SET password = %s WHERE id = %s"
                
                with self.connection.cursor() as cursor:
                    cursor.execute(query, (password_hash, user_id))
                    self.connection.commit()
                    
                return True
            except Exception as e:
                logging.error(f"❌ Error actualizando hash de contraseña: {e}")
                try:
                    self.connection.rollback()
                except:
                    pass
                return False
    
    def get_todos_usuarios(self) -> List[Dict]:
        """
        Obtiene todos los usuarios del sistema
        
        Returns:
            list: Lista de usuarios
        """
        with self._lock:
            try:
                if not self._ensure_connection():
                    return []
                    
                query = """
                    SELECT username, nombre_completo, rol, departamento, activo, fecha_creacion
                    FROM usuarios
                    ORDER BY nombre_completo
                """
                
                with self.connection.cursor() as cursor:
                    cursor.execute(query)
                    usuarios = cursor.fetchall()
                
                # Convertir fechas a formato ISO
                for user in usuarios:
                    if user.get('fecha_creacion'):
                        user['fecha_creacion'] = user['fecha_creacion'].isoformat()
                
                logging.info(f"✅ Obtenidos {len(usuarios)} usuarios")
                return usuarios
                
            except Exception as e:
                logging.error(f"❌ Error obteniendo usuarios: {e}")
                return []
    
    def crear_usuario(self, datos: Dict) -> Optional[Dict]:
        """
        Crea un nuevo usuario con contraseña hasheada
        
        Args:
            datos (dict): Datos del usuario
                - username (str)
                - password (str)
                - nombre_completo (str)
                - rol (str)
                - departamento (str)
            
        Returns:
            dict: Usuario creado o None si falla
        """
        with self._lock:
            try:
                if not self._ensure_connection():
                    return None

                # Hash de la contraseña
                password = datos.get('password')
                try:
                    from security import hash_password
                    password_hash = hash_password(password)
                    logging.info("🔐 Contraseña hasheada para nuevo usuario")
                except ImportError:
                    password_hash = password
                    logging.warning("⚠️ security.py no disponible, guardando contraseña sin hash")
                
                query = """
                    INSERT INTO usuarios (username, password, nombre_completo, rol, departamento, activo)
                    VALUES (%s, %s, %s, %s, %s, TRUE)
                """
                
                values = (
                    datos.get('username'),
                    password_hash,  # Usa el hash en lugar del texto plano
                    datos.get('nombre_completo'),
                    datos.get('rol'),
                    datos.get('departamento')
                )
                
                with self.connection.cursor() as cursor:
                    cursor.execute(query, values)
                    self.connection.commit()
                
                logging.info(f"✅ Usuario creado: {datos.get('username')}")
                return self.get_usuario_por_username(datos.get('username'))
                
            except Exception as e:
                logging.error(f"❌ Error creando usuario: {e}")
                try:
                    self.connection.rollback()
                except:
                    pass
                return None
    
    def get_usuario_por_username(self, username: str) -> Optional[Dict]:
        """
        Obtiene un usuario específico por username
        
        Args:
            username (str): Username del usuario
            
        Returns:
            dict: Usuario o None
        """
        with self._lock:
            try:
                if not self._ensure_connection():
                    return None
                    
                query = """
                    SELECT username, nombre_completo, rol, departamento, activo, fecha_creacion
                    FROM usuarios
                    WHERE username = %s
                """
                
                with self.connection.cursor() as cursor:
                    cursor.execute(query, (username,))
                    usuario = cursor.fetchone()
                
                if usuario and usuario.get('fecha_creacion'):
                    usuario['fecha_creacion'] = usuario['fecha_creacion'].isoformat()
                
                return usuario
                
            except Exception as e:
                logging.error(f"❌ Error obteniendo usuario {username}: {e}")
                return None
    
    def actualizar_estado_usuario(self, username: str, activo: bool) -> bool:
        """
        Actualiza el estado activo/inactivo de un usuario
        
        Args:
            username (str): Username del usuario
            activo (bool): Nuevo estado
            
        Returns:
            bool: True si se actualizó correctamente
        """
        with self._lock:
            try:
                if not self._ensure_connection():
                    return False
                    
                query = """
                    UPDATE usuarios
                    SET activo = %s
                    WHERE username = %s
                """
                
                with self.connection.cursor() as cursor:
                    cursor.execute(query, (activo, username))
                    self.connection.commit()
                    
                    if cursor.rowcount > 0:
                        logging.info(f"✅ Usuario {username} {'activado' if activo else 'desactivado'}")
                        return True
                    else:
                        logging.warning(f"⚠️ Usuario {username} no encontrado")
                        return False
                    
            except Exception as e:
                logging.error(f"❌ Error actualizando usuario {username}: {e}")
                try:
                    self.connection.rollback()
                except:
                    pass
                return False
    
    def eliminar_usuario(self, username: str) -> bool:
        """
        Elimina un usuario del sistema
        
        Args:
            username (str): Username del usuario
            
        Returns:
            bool: True si se eliminó correctamente
        """
        with self._lock:
            try:
                if not self._ensure_connection():
                    return False
                    
                query = "DELETE FROM usuarios WHERE username = %s"
                
                with self.connection.cursor() as cursor:
                    cursor.execute(query, (username,))
                    self.connection.commit()
                    
                    if cursor.rowcount > 0:
                        logging.info(f"🗑️ Usuario {username} eliminado")
                        return True
                    else:
                        logging.warning(f"⚠️ Usuario {username} no encontrado")
                        return False
                    
            except Exception as e:
                logging.error(f"❌ Error eliminando usuario {username}: {e}")
                try:
                    self.connection.rollback()
                except:
                    pass
                return False
    
    def registrar_sesion(self, username: str, ip_address: str) -> bool:
        """
        Registra una sesión de usuario
        
        Args:
            username (str): Username del usuario
            ip_address (str): IP del cliente
            
        Returns:
            bool: True si se registró correctamente
        """
        if not self._ensure_connection():
            logging.error("❌ No hay conexión MySQL disponible para registrar sesión")
            return False
        
        with self._lock:
            try:
                query = """
                    INSERT INTO sesiones (username, ip_address, activa)
                    VALUES (%s, %s, TRUE)
                """
                
                with self.connection.cursor() as cursor:
                    cursor.execute(query, (username, ip_address))
                    self.connection.commit()
                
                logging.info(f"📝 Sesión registrada: {username} desde {ip_address}")
                return True
                
            except Exception as e:
                logging.error(f"❌ Error registrando sesión: {e}")
                try:
                    self.connection.rollback()
                except:
                    pass
                return False

# =========================================================================
    # MÉTODOS PARA GESTIÓN DE MESAS Y RFID
    # =========================================================================
    
    def get_todas_mesas(self, activas_solo=True):
        """
        Obtiene todas las mesas de la base de datos
        
        Args:
            activas_solo (bool): Si True, solo devuelve mesas activas
            
        Returns:
            list: Lista de diccionarios con datos de mesas
        """
        with self._lock:
            try:
                if not self._ensure_connection():
                    logging.error("❌ No hay conexión MySQL disponible para cargar mesas")
                    return []
                
                query = """
                    SELECT 
                        id,
                        departamento,
                        puesto,
                        ip,
                        nombre_puesto,
                        activo,
                        fecha_creacion,
                        fecha_modificacion
                    FROM mesas
                """
                
                if activas_solo:
                    query += " WHERE activo = TRUE"
                
                query += " ORDER BY departamento, puesto"
                
                with self.connection.cursor() as cursor:
                    cursor.execute(query)
                    mesas = cursor.fetchall()
                
                logging.info(f"✅ Obtenidas {len(mesas)} mesas")
                return mesas
                
            except Exception as e:
                logging.error(f"❌ Error obteniendo mesas: {e}")
                return []

    def get_mesas_por_departamento(self, departamento, activas_solo=True):
        """
        Obtiene mesas de un departamento específico
        
        Args:
            departamento (str): Nombre del departamento
            activas_solo (bool): Si True, solo devuelve mesas activas
            
        Returns:
            list: Lista de diccionarios con datos de mesas
        """
        if not self._ensure_connection():
            return []
        
        with self._lock:
            try:
                query = """
                    SELECT 
                        id,
                        departamento,
                        puesto,
                        ip,
                        nombre_puesto,
                        activo
                    FROM mesas
                    WHERE departamento = %s
                """
                
                params = [departamento.lower()]
                
                if activas_solo:
                    query += " AND activo = TRUE"
                
                query += " ORDER BY puesto"
                
                with self.connection.cursor() as cursor:
                    cursor.execute(query, params)
                    return cursor.fetchall()
                    
            except Exception as e:
                logging.error(f"❌ Error obteniendo mesas del departamento {departamento}: {e}")
                import traceback
                logging.error(traceback.format_exc())
                return []

    def get_mesa_por_ip(self, ip):
        """
        Obtiene una mesa por su IP
        
        Args:
            ip (str): Dirección IP de la mesa
            
        Returns:
            dict: Datos de la mesa o None
        """
        if not self._ensure_connection():
            return None
        
        with self._lock:
            try:
                query = """
                    SELECT 
                        id,
                        departamento,
                        puesto,
                        ip,
                        nombre_puesto,
                        activo
                    FROM mesas
                    WHERE ip = %s
                """
                
                with self.connection.cursor() as cursor:
                    cursor.execute(query, (ip,))
                    return cursor.fetchone()
                    
            except Exception as e:
                logging.error(f"❌ Error obteniendo mesa por IP {ip}: {e}")
                import traceback
                logging.error(traceback.format_exc())
                return None

    def get_todos_rfid(self, activos_solo=True):
        """
        Obtiene todos los dispositivos RFID
        
        Args:
            activos_solo (bool): Si True, solo devuelve dispositivos activos
            
        Returns:
            list: Lista de diccionarios con datos de RFID
        """
        with self._lock:
            try:
                if not self._ensure_connection():
                    return []
                    
                query = """
                    SELECT 
                        id,
                        departamento,
                        puesto,
                        ip,
                        nombre_dispositivo,
                        activo,
                        fecha_creacion,
                        fecha_modificacion
                    FROM dispositivos_rfid
                """
                
                if activos_solo:
                    query += " WHERE activo = TRUE"
                
                query += " ORDER BY departamento, puesto"
                
                with self.connection.cursor() as cursor:
                    cursor.execute(query)
                    rfids = cursor.fetchall()
                
                logging.info(f"✅ Obtenidos {len(rfids)} dispositivos RFID")
                return rfids
                
            except Exception as e:
                logging.error(f"❌ Error obteniendo dispositivos RFID: {e}")
                return []

    def get_rfid_por_departamento(self, departamento, activos_solo=True):
        """
        Obtiene dispositivos RFID de un departamento específico
        
        Args:
            departamento (str): Nombre del departamento
            activos_solo (bool): Si True, solo devuelve dispositivos activos
            
        Returns:
            list: Lista de diccionarios con datos de RFID
        """
        if not self._ensure_connection():
            return []
        
        with self._lock:
            try:
                query = """
                    SELECT 
                        id,
                        departamento,
                        puesto,
                        ip,
                        nombre_dispositivo,
                        activo
                    FROM dispositivos_rfid
                    WHERE departamento = %s
                """
                
                params = [departamento.lower()]
                
                if activos_solo:
                    query += " AND activo = TRUE"
                
                query += " ORDER BY puesto"
                
                with self.connection.cursor() as cursor:
                    cursor.execute(query, params)
                    return cursor.fetchall()
                    
            except Exception as e:
                logging.error(f"❌ Error obteniendo RFID del departamento {departamento}: {e}")
                import traceback
                logging.error(traceback.format_exc())
                return []

    def get_rfid_por_puesto(self, departamento, puesto):
        """
        Obtiene el dispositivo RFID de un puesto específico
        
        Args:
            departamento (str): Nombre del departamento
            puesto (int): Número de puesto
            
        Returns:
            dict: Datos del dispositivo RFID o None
        """
        if not self._ensure_connection():
            return None
        
        with self._lock:
            try:
                query = """
                    SELECT 
                        id,
                        departamento,
                        puesto,
                        ip,
                        nombre_dispositivo,
                        activo
                    FROM dispositivos_rfid
                    WHERE departamento = %s AND puesto = %s
                """
                
                with self.connection.cursor() as cursor:
                    cursor.execute(query, (departamento.lower(), puesto))
                    return cursor.fetchone()
                    
            except Exception as e:
                logging.error(f"❌ Error obteniendo RFID para {departamento}-{puesto}: {e}")
                import traceback
                logging.error(traceback.format_exc())
                return None

    def crear_mesa(self, departamento, puesto, ip, nombre_puesto=None):
        """
        Crea una nueva mesa en la base de datos
        
        Args:
            departamento (str): Nombre del departamento
            puesto (int): Número de puesto
            ip (str): Dirección IP
            nombre_puesto (str): Nombre del puesto (opcional)
            
        Returns:
            bool: True si se creó exitosamente
        """
        if not self._ensure_connection():
            return False
        
        with self._lock:
            try:
                if not nombre_puesto:
                    dept_prefix = {
                        'packing': 'PACK',
                        'return': 'RET',
                        'vas': 'VAS'
                    }.get(departamento.lower(), departamento.upper())
                    nombre_puesto = f"{dept_prefix}-{puesto}"
                
                query = """
                    INSERT INTO mesas (departamento, puesto, ip, nombre_puesto, activo)
                    VALUES (%s, %s, %s, %s, TRUE)
                """
                
                with self.connection.cursor() as cursor:
                    cursor.execute(query, (departamento.lower(), puesto, ip, nombre_puesto))
                    self.connection.commit()
                
                logging.info(f"✅ Mesa creada: {nombre_puesto}")
                return True
                
            except Exception as e:
                logging.error(f"❌ Error creando mesa: {e}")
                import traceback
                logging.error(traceback.format_exc())
                try:
                    self.connection.rollback()
                except:
                    pass
                return False

    def actualizar_mesa(self, departamento, puesto, ip=None, activo=None):
        """
        Actualiza datos de una mesa
        
        Args:
            departamento (str): Nombre del departamento
            puesto (int): Número de puesto
            ip (str): Nueva IP (opcional)
            activo (bool): Estado activo/inactivo (opcional)
            
        Returns:
            bool: True si se actualizó exitosamente
        """
        if not self._ensure_connection():
            return False
        
        with self._lock:
            try:
                updates = []
                params = []
                
                if ip is not None:
                    updates.append("ip = %s")
                    params.append(ip)
                
                if activo is not None:
                    updates.append("activo = %s")
                    params.append(activo)
                
                if not updates:
                    return False
                
                params.extend([departamento.lower(), puesto])
                
                query = f"""
                    UPDATE mesas 
                    SET {', '.join(updates)}
                    WHERE departamento = %s AND puesto = %s
                """
                
                with self.connection.cursor() as cursor:
                    cursor.execute(query, tuple(params))
                    self.connection.commit()
                
                logging.info(f"✅ Mesa actualizada: {departamento}-{puesto}")
                return True
                
            except Exception as e:
                logging.error(f"❌ Error actualizando mesa: {e}")
                import traceback
                logging.error(traceback.format_exc())
                try:
                    self.connection.rollback()
                except:
                    pass
                return False

    def crear_rfid(self, departamento, puesto, ip, nombre_dispositivo=None):
        """
        Crea un nuevo dispositivo RFID
        
        Args:
            departamento (str): Nombre del departamento
            puesto (int): Número de puesto
            ip (str): Dirección IP
            nombre_dispositivo (str): Nombre del dispositivo (opcional)
            
        Returns:
            bool: True si se creó exitosamente
        """
        if not self._ensure_connection():
            return False
        
        with self._lock:
            try:
                if not nombre_dispositivo:
                    dept_prefix = {
                        'packing': 'PACK',
                        'return': 'RET',
                        'vas': 'VAS'
                    }.get(departamento.lower(), departamento.upper())
                    nombre_dispositivo = f"RFID-{dept_prefix}-{puesto}"
                
                query = """
                    INSERT INTO dispositivos_rfid (departamento, puesto, ip, nombre_dispositivo, activo)
                    VALUES (%s, %s, %s, %s, TRUE)
                """
                
                with self.connection.cursor() as cursor:
                    cursor.execute(query, (departamento.lower(), puesto, ip, nombre_dispositivo))
                    self.connection.commit()
                
                logging.info(f"✅ RFID creado: {nombre_dispositivo}")
                return True
                
            except Exception as e:
                logging.error(f"❌ Error creando dispositivo RFID: {e}")
                import traceback
                logging.error(traceback.format_exc())
                try:
                    self.connection.rollback()
                except:
                    pass
                return False

    def actualizar_rfid(self, departamento, puesto, ip=None, activo=None):
        """
        Actualiza datos de un dispositivo RFID
        
        Args:
            departamento (str): Nombre del departamento
            puesto (int): Número de puesto
            ip (str): Nueva IP (opcional)
            activo (bool): Estado activo/inactivo (opcional)
            
        Returns:
            bool: True si se actualizó exitosamente
        """
        if not self._ensure_connection():
            return False
        
        with self._lock:
            try:
                updates = []
                params = []
                
                if ip is not None:
                    updates.append("ip = %s")
                    params.append(ip)
                
                if activo is not None:
                    updates.append("activo = %s")
                    params.append(activo)
                
                if not updates:
                    return False
                
                params.extend([departamento.lower(), puesto])
                
                query = f"""
                    UPDATE dispositivos_rfid 
                    SET {', '.join(updates)}
                    WHERE departamento = %s AND puesto = %s
                """
                
                with self.connection.cursor() as cursor:
                    cursor.execute(query, tuple(params))
                    self.connection.commit()
                
                logging.info(f"✅ RFID actualizado: {departamento}-{puesto}")
                return True
                
            except Exception as e:
                logging.error(f"❌ Error actualizando dispositivo RFID: {e}")
                import traceback
                logging.error(traceback.format_exc())
                try:
                    self.connection.rollback()
                except:
                    pass
                return False

    # =========================================================================
    # MÉTODOS PARA GESTIÓN DE IMPRESORAS ZEBRA
    # =========================================================================
    
    def get_todas_zebra(self, activas_solo=True):
        """
        Obtiene todas las impresoras Zebra
        
        Args:
            activas_solo (bool): Si True, solo devuelve impresoras activas
            
        Returns:
            list: Lista de diccionarios con datos de impresoras
        """
        with self._lock:
            try:
                if not self._ensure_connection():
                    logging.error("❌ No hay conexión MySQL disponible para cargar impresoras Zebra")
                    return []
                
                query = """
                    SELECT 
                        id,
                        departamento,
                        puesto,
                        ip,
                        puerto,
                        modelo,
                        descripcion,
                        activo,
                        darkness_default,
                        darkness_custom,
                        speed_default,
                        top_default,
                        tear_off_default,
                        left_position,
                        custom_locked,
                        fecha_creacion,
                        fecha_actualizacion
                    FROM impresoras_zebra
                """
                
                if activas_solo:
                    query += " WHERE activo = TRUE"
                
                query += " ORDER BY departamento, puesto"
                
                with self.connection.cursor() as cursor:
                    cursor.execute(query)
                    impresoras = cursor.fetchall()
                
                logging.info(f"✅ Obtenidas {len(impresoras)} impresoras Zebra")
                return impresoras
                
            except Exception as e:
                logging.error(f"❌ Error obteniendo impresoras Zebra: {e}")
                return []
    
    def get_zebra_por_puesto(self, departamento, puesto):
        """
        Obtiene la impresora Zebra de un puesto específico
        
        Args:
            departamento (str): Nombre del departamento
            puesto (int): Número de puesto
            
        Returns:
            dict: Datos de la impresora Zebra o None
        """
        if not self._ensure_connection():
            return None
        
        with self._lock:
            try:
                query = """
                    SELECT 
                        id,
                        departamento,
                        puesto,
                        ip,
                        puerto,
                        modelo,
                        descripcion,
                        activo,
                        darkness_default,
                        speed_default,
                        top_default,
                        tear_off_default
                    FROM impresoras_zebra
                    WHERE departamento = %s AND puesto = %s AND activo = TRUE
                """
                
                with self.connection.cursor() as cursor:
                    cursor.execute(query, (departamento.lower(), puesto))
                    return cursor.fetchone()
                    
            except Exception as e:
                logging.error(f"❌ Error obteniendo impresora Zebra para {departamento}-{puesto}: {e}")
                import traceback
                logging.error(traceback.format_exc())
                return None
    
    def get_zebra_por_departamento(self, departamento, activas_solo=True):
        """
        Obtiene impresoras Zebra de un departamento específico
        
        Args:
            departamento (str): Nombre del departamento
            activas_solo (bool): Si True, solo devuelve impresoras activas
            
        Returns:
            list: Lista de diccionarios con datos de impresoras
        """
        with self._lock:
            if not self._ensure_connection():
                return []
            
            try:
                query = """
                    SELECT 
                        id,
                        departamento,
                        puesto,
                        ip,
                        puerto,
                        modelo,
                        descripcion,
                        activo,
                        darkness_default,
                        speed_default,
                        top_default,
                        tear_off_default
                    FROM impresoras_zebra
                    WHERE departamento = %s
                """
                
                params = [departamento.lower()]
                
                if activas_solo:
                    query += " AND activo = TRUE"
                
                query += " ORDER BY puesto"
                
                with self.connection.cursor() as cursor:
                    cursor.execute(query, params)
                    return cursor.fetchall()
                
            except Exception as e:
                logging.error(f"❌ Error obteniendo impresoras Zebra del departamento {departamento}: {e}")
                return []

    def crear_zebra(self, departamento, puesto, ip, modelo='ZD420/ZD421', descripcion=None):
        """
        Crea una nueva impresora Zebra
        
        Args:
            departamento (str): Nombre del departamento
            puesto (int): Número de puesto
            ip (str): Dirección IP
            modelo (str): Modelo de la impresora
            descripcion (str): Descripción adicional (opcional)
            
        Returns:
            bool: True si se creó exitosamente
        """
        with self._lock:
            if not self._ensure_connection():
                return False
            
            try:
                if not descripcion:
                    dept_prefix = {
                        'packing': 'Packing',
                        'return': 'Return',
                        'vas': 'VAS'
                    }.get(departamento.lower(), departamento.upper())
                    descripcion = f"Impresora Zebra {dept_prefix} Puesto {puesto}"
                
                query = """
                    INSERT INTO impresoras_zebra (departamento, puesto, ip, modelo, descripcion, activo)
                    VALUES (%s, %s, %s, %s, %s, TRUE)
                """
                
                with self.connection.cursor() as cursor:
                    cursor.execute(query, (departamento.lower(), puesto, ip, modelo, descripcion))
                    self.connection.commit()
                
                logging.info(f"✅ Impresora Zebra creada: {departamento}-{puesto}")
                return True
                
            except Exception as e:
                logging.error(f"❌ Error creando impresora Zebra: {e}")
                self.connection.rollback()
                return False

    def actualizar_zebra(self, departamento, puesto, ip=None, activo=None, 
                         darkness_default=None, speed_default=None, 
                         top_default=None, tear_off_default=None):
        """
        Actualiza datos de una impresora Zebra
        
        Args:
            departamento (str): Nombre del departamento
            puesto (int): Número de puesto
            ip (str): Nueva IP (opcional)
            activo (bool): Estado activo/inactivo (opcional)
            darkness_default - tear_off_default: Configuración por defecto
            
        Returns:
            bool: True si se actualizó exitosamente
        """
        with self._lock:
            if not self._ensure_connection():
                return False
            
            try:
                updates = []
                params = []
                
                if ip is not None:
                    updates.append("ip = %s")
                    params.append(ip)
                
                if activo is not None:
                    updates.append("activo = %s")
                    params.append(activo)
                
                if darkness_default is not None:
                    updates.append("darkness_default = %s")
                    params.append(darkness_default)
                
                if speed_default is not None:
                    updates.append("speed_default = %s")
                    params.append(speed_default)
                
                if top_default is not None:
                    updates.append("top_default = %s")
                    params.append(top_default)
                
                if tear_off_default is not None:
                    updates.append("tear_off_default = %s")
                    params.append(tear_off_default)
                
                if not updates:
                    return False
                
                params.extend([departamento.lower(), puesto])
                
                query = f"""
                    UPDATE impresoras_zebra 
                    SET {', '.join(updates)}
                    WHERE departamento = %s AND puesto = %s
                """
                
                with self.connection.cursor() as cursor:
                    cursor.execute(query, tuple(params))
                    self.connection.commit()
                    rows_affected = cursor.rowcount
                
                if rows_affected > 0:
                    logging.info(f"✅ Impresora Zebra actualizada: {departamento}-{puesto}")
                    return True
                else:
                    logging.warning(f"⚠️ Impresora Zebra no encontrada: {departamento}-{puesto}")
                    return False
                
            except Exception as e:
                logging.error(f"❌ Error actualizando impresora Zebra: {e}")
                self.connection.rollback()
                return False

    # =========================================================================
    # MÉTODOS PARA CONFIGURACIÓN MASIVA DE ZEBRAS
    # =========================================================================
    
    def actualizar_configuracion_zebra(self, departamento: str, puesto: int,
                                       darkness_custom: int = None,
                                       left_position: int = None,
                                       top_position: int = None,
                                       custom_locked: bool = False) -> bool:
        """
        Actualiza la configuración personalizada de una impresora Zebra
        
        Args:
            departamento (str): packing, return, vas
            puesto (int): número del puesto
            darkness_custom (int): Contraste personalizado (None = usar default)
            left_position (int): Posición izquierda
            top_position (int): Posición superior
            custom_locked (bool): Si está bloqueada la configuración
            
        Returns:
            bool: True si se actualizó correctamente
        """
        with self._lock:
            if not self._ensure_connection():
                return False
            
            try:
                # Construir UPDATE dinámico solo con los campos que se especifican
                set_clauses = []
                params = []
                
                if darkness_custom is not None:
                    set_clauses.append("darkness_custom = %s")
                    params.append(darkness_custom)
                else:
                    # Si darkness_custom es None, significa resetear al default
                    set_clauses.append("darkness_custom = NULL")
                
                if left_position is not None:
                    set_clauses.append("left_position = %s")
                    params.append(left_position)
                
                if top_position is not None:
                    set_clauses.append("top_position = %s")
                    params.append(top_position)
                
                set_clauses.append("custom_locked = %s")
                params.append(custom_locked)
                
                # Añadir WHERE
                params.extend([departamento, puesto])
                
                query = f"""
                    UPDATE impresoras_zebra
                    SET {', '.join(set_clauses)}
                    WHERE departamento = %s AND puesto = %s
                """
                
                with self.connection.cursor() as cursor:
                    cursor.execute(query, tuple(params))
                    self.connection.commit()
                    rows_affected = cursor.rowcount
                
                if rows_affected > 0:
                    return True
                else:
                    return False
                    
            except Exception as e:
                logging.error(f"❌ Error actualizando configuración Zebra: {e}")
                self.connection.rollback()
                return False
    
    def get_zebras_configuracion(self, departamento: str = None,
                                 puesto_desde: int = None,
                                 puesto_hasta: int = None) -> List[Dict]:
        """
        Obtiene configuraciones de impresoras Zebra con filtros opcionales
        
        Args:
            departamento (str): Filtrar por departamento (opcional)
            puesto_desde (int): Rango desde (opcional)
            puesto_hasta (int): Rango hasta (opcional)
            
        Returns:
            list: Lista de configuraciones de impresoras
        """
        with self._lock:
            if not self._ensure_connection():
                return []
            
            try:
                where_clauses = []
                params = []
                
                if departamento:
                    where_clauses.append("departamento = %s")
                    params.append(departamento)
                
                if puesto_desde is not None:
                    where_clauses.append("puesto >= %s")
                    params.append(puesto_desde)
                
                if puesto_hasta is not None:
                    where_clauses.append("puesto <= %s")
                    params.append(puesto_hasta)
                
                where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
                
                query = f"""
                    SELECT 
                        id, departamento, puesto, ip, puerto, modelo,
                        darkness_default, darkness_custom,
                        top_default, left_position, top_position,
                        custom_locked, activo
                    FROM impresoras_zebra
                    {where_sql}
                    ORDER BY departamento, puesto
                """
                
                with self.connection.cursor() as cursor:
                    cursor.execute(query, tuple(params))
                    return cursor.fetchall()
                    
            except Exception as e:
                logging.error(f"❌ Error obteniendo configuraciones Zebra: {e}")
                return []
    
    def get_zebras_bloqueadas(self) -> List[Dict]:
        with self._lock:
            if not self._ensure_connection():
                return []
            try:
                query = """SELECT departamento, puesto, ip, darkness_custom, left_position, top_position
                    FROM impresoras_zebra WHERE custom_locked = TRUE AND activo = TRUE
                    ORDER BY departamento, puesto"""
                with self.connection.cursor() as cursor:
                    cursor.execute(query)
                    return cursor.fetchall()
            except Exception as e:
                logging.error(f"❌ Error obteniendo impresoras bloqueadas: {e}")
                return []
    
    def desbloquear_zebra(self, departamento: str, puesto: int) -> bool:
        with self._lock:
            if not self._ensure_connection():
                return False
            try:
                query = "UPDATE impresoras_zebra SET custom_locked = FALSE WHERE departamento = %s AND puesto = %s"
                with self.connection.cursor() as cursor:
                    cursor.execute(query, (departamento, puesto))
                    self.connection.commit()
                    if cursor.rowcount > 0:
                        logging.info(f"✅ Impresora desbloqueada: {departamento}-{puesto}")
                        return True
                return False
            except Exception as e:
                logging.error(f"❌ Error desbloqueando: {e}")
                self.connection.rollback()
                return False
    
    def actualizar_configuracion_zebra_parcial(self, departamento: str, puesto: int, **kwargs) -> bool:
        with self._lock:
            if not self._ensure_connection():
                return False
            try:
                set_clauses = []
                params = []
                for field in ['darkness_custom', 'left_position', 'top_position', 'custom_locked']:
                    if field in kwargs:
                        set_clauses.append(f"{field} = %s")
                        params.append(kwargs[field])
                if not set_clauses:
                    return False
                params.extend([departamento, puesto])
                query = f"UPDATE impresoras_zebra SET {', '.join(set_clauses)} WHERE departamento = %s AND puesto = %s"
                with self.connection.cursor() as cursor:
                    cursor.execute(query, tuple(params))
                    self.connection.commit()
                    return True
            except Exception as e:
                logging.error(f"❌ Error actualizando parcial: {e}")
                self.connection.rollback()
                return False
    
    def crear_chequeo_general(self, datos: dict):
        with self._lock:
            if not self._ensure_connection():
                return None
            try:
                query = """INSERT INTO chequeos_generales 
                    (departamento, puesto, usuario_id, usuario_nombre, fecha_inicio, estado)
                    VALUES (%s, %s, %s, %s, NOW(), 'en_progreso')"""
                with self.connection.cursor() as cursor:
                    cursor.execute(query, (datos['departamento'], datos['puesto'],
                        datos.get('usuario_id'), datos.get('usuario_nombre')))
                    self.connection.commit()
                    return cursor.lastrowid
            except Exception as e:
                logging.error(f"❌ Error creando chequeo: {e}")
                self.connection.rollback()
                return None
    
    def actualizar_componente_chequeo(self, chequeo_id: int, componente: str, estado: str) -> bool:
        with self._lock:
            if not self._ensure_connection():
                return False
            try:
                query = f"UPDATE chequeos_generales SET {componente} = %s WHERE id = %s"
                with self.connection.cursor() as cursor:
                    cursor.execute(query, (estado, chequeo_id))
                    self.connection.commit()
                    return cursor.rowcount > 0
            except Exception as e:
                logging.error(f"❌ Error: {e}")
                self.connection.rollback()
                return False
    
    def finalizar_chequeo(self, chequeo_id: int, observaciones: str = '') -> bool:
        with self._lock:
            if not self._ensure_connection():
                return False
            try:
                query = """UPDATE chequeos_generales 
                    SET estado = 'completado', fecha_fin = NOW(), observaciones = %s WHERE id = %s"""
                with self.connection.cursor() as cursor:
                    cursor.execute(query, (observaciones, chequeo_id))
                    self.connection.commit()
                    return True
            except Exception as e:
                logging.error(f"❌ Error: {e}")
                self.connection.rollback()
                return False
    
    def guardar_progreso_chequeo(self, session_id: str, datos: dict) -> bool:
        with self._lock:
            if not self._ensure_connection():
                return False
            try:
                import json
                query = """INSERT INTO chequeos_progreso 
                    (session_id, usuario_id, departamento, rango_desde, rango_hasta, 
                    filtro, puestos_completados, ultimo_puesto)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE puestos_completados = VALUES(puestos_completados),
                    ultimo_puesto = VALUES(ultimo_puesto)"""
                with self.connection.cursor() as cursor:
                    cursor.execute(query, (session_id, datos['usuario_id'], datos['departamento'],
                        datos['rango_desde'], datos['rango_hasta'], datos['filtro'],
                        json.dumps(datos['puestos_completados']), datos['ultimo_puesto']))
                    self.connection.commit()
                    return True
            except Exception as e:
                logging.error(f"❌ Error: {e}")
                self.connection.rollback()
                return False
    
    def obtener_progreso_chequeo(self, session_id: str):
        with self._lock:
            if not self._ensure_connection():
                return None
            try:
                query = "SELECT * FROM chequeos_progreso WHERE session_id = %s"
                with self.connection.cursor() as cursor:
                    cursor.execute(query, (session_id,))
                    return cursor.fetchone()
            except Exception as e:
                logging.error(f"❌ Error: {e}")
                return None

    def guardar_chequeo_completo(self, departamento: str, puesto: int, 
                                  componentes: dict, observaciones: str = '',
                                  usuario_id: int = None, usuario_nombre: str = None) -> int:
        """
        Guarda un chequeo completo con todos los componentes.
        
        Args:
            departamento: Departamento del puesto
            puesto: Número de puesto
            componentes: Dict con estado de cada componente {'pantalla': 'bueno', 'ordenador': 'mal', ...}
            observaciones: Texto con observaciones adicionales
            usuario_id: ID del usuario que realiza el chequeo
            usuario_nombre: Nombre del usuario
            
        Returns:
            int: ID del chequeo creado o None si falla
        """
        with self._lock:
            if not self._ensure_connection():
                return None
            
            try:
                # Mapear componentes a columnas de la tabla
                comp_cols = ['pantalla', 'ordenador', 'teclado_cherry', 'pistola', 
                             'impresora', 'raton', 'cognex', 'rfid']
                
                # Construir valores para cada componente
                valores_componentes = []
                for comp in comp_cols:
                    estado = componentes.get(comp, 'pendiente')
                    # Normalizar valores
                    if estado in ['bien', 'ok', 'bueno']:
                        estado = 'bueno'
                    elif estado in ['mal', 'malo', 'error']:
                        estado = 'malo'
                    else:
                        estado = 'pendiente'
                    valores_componentes.append(estado)
                
                query = """
                    INSERT INTO chequeos_generales 
                    (departamento, puesto, usuario_id, usuario_nombre, fecha_inicio, fecha_fin, 
                     estado, pantalla, ordenador, teclado_cherry, pistola, impresora, 
                     raton, cognex, rfid, observaciones)
                    VALUES (%s, %s, %s, %s, NOW(), NOW(), 'completado', 
                            %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                
                params = (
                    departamento, puesto, usuario_id, usuario_nombre,
                    *valores_componentes,
                    observaciones or ''
                )
                
                with self.connection.cursor() as cursor:
                    cursor.execute(query, params)
                    self.connection.commit()
                    chequeo_id = cursor.lastrowid
                    logging.info(f"✅ Chequeo guardado: {departamento.upper()}-{puesto} (ID: {chequeo_id})")
                    return chequeo_id
                    
            except Exception as e:
                logging.error(f"❌ Error guardando chequeo completo: {e}")
                try:
                    self.connection.rollback()
                except:
                    pass
                return None

# =============================================================================
# FIN DEL MÓDULO
# =============================================================================