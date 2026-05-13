"""
=============================================================================
MÓDULO DE GESTIÓN DE INCIDENCIAS - SQLite
=============================================================================
Base de datos: incidencias.db
Versión: 1.0 - Adaptación de MySQL a SQLite
=============================================================================
"""

import sqlite3
import logging
import threading
import os
from datetime import datetime
from typing import List, Dict, Optional

class SQLiteIncidencias:
    """
    Clase para gestionar incidencias en SQLite
    Con inicialización automática del esquema.
    """
    
    _lock = threading.RLock()
    
    def __init__(self):
        """
        Inicializa la conexión a SQLite y asegura que las tablas existan.
        """
        try:
            from config import SQLiteConfig
            config = SQLiteConfig.get_config()
            self.db_path = config['database_path']
        except ImportError:
            # Fallback
            self.db_path = os.path.join(os.path.dirname(__file__), 'database', 'incidencias.db')
        
        # Asegurar que el directorio existe
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        self._init_db()

    def _get_connection(self):
        """Retorna una conexión a SQLite con soporte para diccionarios"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = self._dict_factory
        return conn

    def _dict_factory(self, cursor, row):
        """Convierte las filas de SQLite en diccionarios"""
        d = {}
        for idx, col in enumerate(cursor.description):
            d[col[0]] = row[idx]
        return d

    def _init_db(self):
        """Inicializa las tablas si no existen"""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            try:
                # Tabla de incidencias
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS incidencias (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    departamento TEXT NOT NULL,
                    puesto INTEGER NOT NULL,
                    categoria TEXT NOT NULL,
                    descripcion TEXT,
                    prioridad TEXT DEFAULT 'MEDIA',
                    estado TEXT DEFAULT 'pendiente',
                    reportado_por TEXT NOT NULL,
                    reportado_por_username TEXT NOT NULL,
                    resuelto_por TEXT,
                    fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP,
                    fecha_actualizacion DATETIME DEFAULT CURRENT_TIMESTAMP,
                    fecha_resolucion DATETIME,
                    notas_resolucion TEXT
                )
                ''')

                # Tabla de comentarios
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS comentarios_incidencias (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    incidencia_id INTEGER NOT NULL,
                    usuario TEXT NOT NULL,
                    username TEXT NOT NULL,
                    comentario TEXT NOT NULL,
                    fecha_comentario DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (incidencia_id) REFERENCES incidencias(id) ON DELETE CASCADE
                )
                ''')

                # Tabla de tipos de incidencias
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS tipos_incidencias (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    codigo TEXT NOT NULL UNIQUE,
                    descripcion TEXT NOT NULL,
                    categoria TEXT NOT NULL,
                    prioridad TEXT DEFAULT 'MEDIA',
                    activo BOOLEAN DEFAULT 1,
                    fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                ''')
                
                # Insertar tipos básicos si la tabla está vacía
                cursor.execute("SELECT COUNT(*) as count FROM tipos_incidencias")
                if cursor.fetchone()['count'] == 0:
                    tipos = [
                        ('PC_NO_ENCIENDE', 'PC no enciende', 'Hardware', 'ALTA'),
                        ('PC_LENTO', 'PC muy lento', 'Rendimiento', 'MEDIA'),
                        ('SIN_INTERNET', 'Sin conexión a Internet', 'Red', 'ALTA'),
                        ('ERROR_SOFTWARE', 'Error en software/aplicación', 'Software', 'MEDIA'),
                        ('TECLADO_RATON', 'Problema con teclado/ratón', 'Periféricos', 'MEDIA'),
                        ('MONITOR', 'Problema con monitor/pantalla', 'Hardware', 'ALTA'),
                        ('IMPRESORA', 'Problema con impresora', 'Periféricos', 'MEDIA'),
                        ('RFID_ERROR', 'Error en lector RFID', 'Hardware', 'ALTA'),
                        ('SIN_ACCESO', 'Sin acceso a sistema', 'Accesos', 'CRÍTICA'),
                        ('OTRO', 'Otro problema', 'General', 'BAJA')
                    ]
                    cursor.executemany(
                        "INSERT INTO tipos_incidencias (codigo, descripcion, categoria, prioridad) VALUES (?, ?, ?, ?)",
                        tipos
                    )

                # Tabla de historial
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS historial_incidencias (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    incidencia_id INTEGER NOT NULL,
                    tipo_evento TEXT NOT NULL,
                    descripcion TEXT,
                    usuario TEXT,
                    username TEXT,
                    datos_adicionales TEXT,
                    fecha_evento DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (incidencia_id) REFERENCES incidencias(id) ON DELETE CASCADE
                )
                ''')

                # Tabla de usuarios
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS usuarios (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    password TEXT NOT NULL,
                    nombre_completo TEXT NOT NULL,
                    rol TEXT NOT NULL,
                    departamento TEXT,
                    activo BOOLEAN DEFAULT 1
                )
                ''')

                # Insertar usuarios básicos si la tabla está vacía
                cursor.execute("SELECT COUNT(*) as count FROM usuarios")
                if cursor.fetchone()['count'] == 0:
                    cursor.execute("""
                        INSERT INTO usuarios (username, password, nombre_completo, rol, departamento)
                        VALUES ('admin', 'admin123', 'Administrador IT', 'IT_ADMIN', 'IT')
                    """)

                # Tabla de mesas
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS mesas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    departamento TEXT NOT NULL,
                    puesto INTEGER NOT NULL,
                    ip TEXT,
                    activa BOOLEAN DEFAULT 1
                )
                ''')

                # Tabla de rfid
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS rfid (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    departamento TEXT NOT NULL,
                    puesto INTEGER NOT NULL,
                    ip TEXT,
                    nombre_dispositivo TEXT,
                    activo BOOLEAN DEFAULT 1
                )
                ''')

                # Tabla de impresoras_zebra
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS impresoras_zebra (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    departamento TEXT NOT NULL,
                    puesto INTEGER NOT NULL,
                    ip TEXT,
                    puerto INTEGER DEFAULT 9100,
                    modelo TEXT DEFAULT 'ZD421',
                    darkness_default INTEGER DEFAULT 15,
                    darkness_custom INTEGER,
                    speed_default INTEGER DEFAULT 4,
                    top_default INTEGER DEFAULT 0,
                    tear_off_default INTEGER DEFAULT 0,
                    left_position INTEGER DEFAULT 0,
                    custom_locked BOOLEAN DEFAULT 0,
                    activo BOOLEAN DEFAULT 1
                )
                ''')

                # Trigger para actualizar fecha_actualizacion
                cursor.execute('''
                CREATE TRIGGER IF NOT EXISTS update_incidencias_timestamp 
                AFTER UPDATE ON incidencias
                FOR EACH ROW
                BEGIN
                    UPDATE incidencias SET fecha_actualizacion = CURRENT_TIMESTAMP WHERE id = OLD.id;
                END
                ''')

                conn.commit()
                logging.info(f"✅ Base de datos SQLite inicializada en: {self.db_path}")
            except Exception as e:
                logging.error(f"❌ Error inicializando base de datos SQLite: {e}")
            finally:
                conn.close()

    def __getattr__(self, name):
        """Fallback para métodos de MySQLIncidencias no implementados aún en SQLite"""
        def mock_method(*args, **kwargs):
            logging.warning(f"⚠️ SQLiteIncidencias: El método '{name}' no está implementado, devolviendo []")
            return []
        return mock_method

    def is_connected(self) -> bool:
        return True

    def close(self):
        pass

    def get_todas_mesas(self, activas_solo: bool = False) -> List[Dict]:
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                query = "SELECT departamento, puesto, ip, nombre_puesto, activo FROM mesas"
                if activas_solo:
                    query += " WHERE activo = 1"
                cursor.execute(query)
                return cursor.fetchall()
            finally:
                conn.close()

    def get_todos_rfid(self, activos_solo: bool = False) -> List[Dict]:
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                query = "SELECT departamento, puesto, ip, nombre_dispositivo, activo FROM dispositivos_rfid"
                if activos_solo:
                    query += " WHERE activo = 1"
                cursor.execute(query)
                return cursor.fetchall()
            finally:
                conn.close()

    def get_todas_zebras(self, activas_solo: bool = False) -> List[Dict]:
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                query = "SELECT * FROM impresoras_zebra"
                if activas_solo:
                    query += " WHERE activo = 1"
                cursor.execute(query)
                return cursor.fetchall()
            finally:
                conn.close()

    def get_zebras_configuracion(self, activas_solo: bool = False, departamento: str = None) -> List[Dict]:
        return self.get_todas_zebras(activas_solo)

    def exportar_incidencias_csv(self, fecha_inicio: str = None, fecha_fin: str = None, departamento: str = None) -> List[Dict]:
        return self.get_incidencias(fecha_inicio=fecha_inicio, fecha_fin=fecha_fin, departamento=departamento)

    def get_todos_usuarios(self, activos_solo=True) -> List[Dict]:
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                query = "SELECT * FROM usuarios"
                if activos_solo: query += " WHERE activo = 1"
                cursor.execute(query)
                return cursor.fetchall()
            except Exception as e:
                logging.error(f"❌ Error obteniendo usuarios: {e}")
                return []
            finally:
                conn.close()

    def get_todas_mesas(self, activas_solo=True) -> List[Dict]:
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                query = "SELECT * FROM mesas"
                if activas_solo: query += " WHERE activa = 1"
                cursor.execute(query)
                return cursor.fetchall()
            except Exception as e:
                logging.error(f"❌ Error obteniendo mesas: {e}")
                return []
            finally:
                conn.close()

    def get_todos_rfid(self, activos_solo=True) -> List[Dict]:
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                query = "SELECT * FROM rfid"
                if activos_solo: query += " WHERE activo = 1"
                cursor.execute(query)
                return cursor.fetchall()
            except Exception as e:
                logging.error(f"❌ Error obteniendo rfid: {e}")
                return []
            finally:
                conn.close()

    def get_todas_zebra(self, activas_solo=True) -> List[Dict]:
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                query = "SELECT * FROM impresoras_zebra"
                if activas_solo: query += " WHERE activo = 1"
                cursor.execute(query)
                return cursor.fetchall()
            except Exception as e:
                logging.error(f"❌ Error obteniendo impresoras: {e}")
                return []
            finally:
                conn.close()

    def verificar_credenciales(self, username, password) -> Optional[Dict]:
        """Verifica credenciales de usuario"""
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM usuarios WHERE username = ? AND password = ?", (username, password))
                user = cursor.fetchone()
                if user:
                    # Asegurar que el diccionario tenga todos los campos esperados
                    return {
                        'username': user['username'],
                        'nombre_completo': user['nombre_completo'],
                        'rol': user['rol'],
                        'departamento': user['departamento'],
                        'activo': user.get('activo', 1)
                    }
                return None
            except Exception as e:
                logging.error(f"❌ Error verificando credenciales: {e}")
                return None
            finally:
                conn.close()

    def get_motivos_pausa(self, activos_solo=True) -> List[Dict]:
        """Mock de motivos de pausa para evitar errores en dashboard"""
        return [
            {'id': 1, 'nombre': 'Descanso', 'codigo': 'BREAK'},
            {'id': 2, 'nombre': 'Reunión', 'codigo': 'MEETING'},
            {'id': 3, 'nombre': 'Formación', 'codigo': 'TRAINING'},
            {'id': 4, 'nombre': 'Avería', 'codigo': 'BREAKDOWN'}
        ]

    def get_distribucion_categorias(self) -> Dict:
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT categoria, COUNT(*) as count FROM incidencias GROUP BY categoria")
                rows = cursor.fetchall()
                return {
                    'labels': [r['categoria'] for r in rows],
                    'data': [r['count'] for r in rows]
                }
            except Exception:
                return {'labels': [], 'data': []}
            finally:
                conn.close()

    def get_incidencias_por_departamento(self) -> Dict:
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT departamento, COUNT(*) as count FROM incidencias GROUP BY departamento")
                rows = cursor.fetchall()
                return {
                    'labels': [r['departamento'] for r in rows],
                    'data': [r['count'] for r in rows]
                }
            except Exception:
                return {'labels': [], 'data': []}
            finally:
                conn.close()

    def registrar_sesion(self, username, ip_address):
        """Mock de registro de sesión"""
        return True

    def get_todas_incidencias(self) -> List[Dict]:
        return self.get_incidencias()

    def get_incidencias(self, fecha_inicio: str = None, fecha_fin: str = None,
                        departamento: str = None, estado: str = None) -> List[Dict]:
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                where_clauses = []
                params = []
                if fecha_inicio:
                    where_clauses.append("DATE(i.fecha_creacion) >= ?")
                    params.append(fecha_inicio)
                if fecha_fin:
                    where_clauses.append("DATE(i.fecha_creacion) <= ?")
                    params.append(fecha_fin)
                if departamento and departamento != 'todos':
                    where_clauses.append("i.departamento = ?")
                    params.append(departamento)
                if estado and estado != 'todos':
                    where_clauses.append("i.estado = ?")
                    params.append(estado)
                where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
                query = f"""
                    SELECT 
                        i.*,
                        (SELECT COUNT(*) FROM comentarios_incidencias c WHERE c.incidencia_id = i.id) as total_comentarios
                    FROM incidencias i
                    {where_sql}
                    ORDER BY 
                        CASE i.estado 
                            WHEN 'pendiente' THEN 1 
                            WHEN 'en_proceso' THEN 2 
                            WHEN 'pausada' THEN 3
                            WHEN 'resuelta' THEN 4 
                            ELSE 5 END,
                        i.fecha_creacion DESC
                """
                cursor.execute(query, params)
                return cursor.fetchall()
            except Exception as e:
                logging.error(f"❌ Error obteniendo incidencias: {e}")
                return []
            finally:
                conn.close()

    def crear_incidencia(self, datos: Dict, reportado_por_nombre: str, reportado_por_username: str) -> Optional[Dict]:
        with self._lock:
            conn = self._get_connection()
            try:
                puesto = datos.get('puesto', '')
                if isinstance(puesto, str) and '-' in puesto:
                    puesto_num = int(puesto.split('-')[1])
                else:
                    puesto_num = int(puesto)
                
                query = """
                    INSERT INTO incidencias 
                    (departamento, puesto, categoria, descripcion, prioridad, 
                     estado, reportado_por, reportado_por_username)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """
                
                values = (
                    datos.get('departamento', '').lower(),
                    puesto_num,
                    datos.get('categoria', ''),
                    datos.get('descripcion', ''),
                    datos.get('prioridad', 'MEDIA'),
                    'pendiente',
                    reportado_por_nombre,
                    reportado_por_username
                )
                
                cursor = conn.cursor()
                cursor.execute(query, values)
                incidencia_id = cursor.lastrowid
                
                # Registrar en historial
                cursor.execute("""
                    INSERT INTO historial_incidencias 
                    (incidencia_id, tipo_evento, descripcion, usuario, username)
                    VALUES (?, ?, ?, ?, ?)
                """, (incidencia_id, 'CREACION', 'Incidencia reportada', reportado_por_nombre, reportado_por_username))
                
                conn.commit()
                return self.get_incidencia_por_id(incidencia_id)
            except Exception as e:
                logging.error(f"❌ Error creando incidencia: {e}")
                conn.rollback()
                return None
            finally:
                conn.close()

    def get_incidencia_por_id(self, incidencia_id: int) -> Optional[Dict]:
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM incidencias WHERE id = ?", (incidencia_id,))
                incidencia = cursor.fetchone()
                if incidencia:
                    cursor.execute("SELECT * FROM comentarios_incidencias WHERE incidencia_id = ?", (incidencia_id,))
                    incidencia['comentarios'] = cursor.fetchall()
                return incidencia
            except Exception as e:
                logging.error(f"❌ Error obteniendo incidencia {incidencia_id}: {e}")
                return None
            finally:
                conn.close()

    def actualizar_estado_incidencia(self, incidencia_id: int, nuevo_estado: str, 
                                    resuelto_por: str = None, notas: str = None,
                                    resuelto_por_username: str = None) -> Optional[Dict]:
        with self._lock:
            conn = self._get_connection()
            try:
                incidencia_actual = self.get_incidencia_por_id(incidencia_id)
                if not incidencia_actual: return None
                
                estado_anterior = incidencia_actual['estado']
                
                cursor = conn.cursor()
                if nuevo_estado == 'resuelta':
                    cursor.execute("""
                        UPDATE incidencias 
                        SET estado = ?, 
                            resuelto_por = ?,
                            notas_resolucion = ?,
                            fecha_resolucion = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (nuevo_estado, resuelto_por, notas, incidencia_id))
                else:
                    cursor.execute("""
                        UPDATE incidencias 
                        SET estado = ?
                        WHERE id = ?
                    """, (nuevo_estado, incidencia_id))
                
                # Registrar Historial
                import json
                tipo_evento = nuevo_estado.upper()
                descripcion_evento = f"Estado cambiado de {estado_anterior} a {nuevo_estado}"
                if notas: descripcion_evento += f" - {notas}"
                
                cursor.execute("""
                    INSERT INTO historial_incidencias 
                    (incidencia_id, tipo_evento, descripcion, usuario, username, datos_adicionales)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (incidencia_id, tipo_evento, descripcion_evento, 
                      resuelto_por or 'Sistema', resuelto_por_username or 'sistema',
                      json.dumps({'anterior': estado_anterior, 'nuevo': nuevo_estado})))
                
                conn.commit()
                return self.get_incidencia_por_id(incidencia_id)
            except Exception as e:
                logging.error(f"❌ Error actualizando incidencia {incidencia_id}: {e}")
                conn.rollback()
                return None
            finally:
                conn.close()

    def get_incidencias_activas_por_puesto(self) -> Dict:
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT departamento, puesto, COUNT(*) as cantidad
                    FROM incidencias
                    WHERE estado IN ('pendiente', 'en_proceso')
                    GROUP BY departamento, puesto
                """)
                resultados = cursor.fetchall()
                
                incidencias_por_puesto = {}
                for row in resultados:
                    dept = row['departamento']
                    puesto = row['puesto']
                    if dept not in incidencias_por_puesto: incidencias_por_puesto[dept] = {}
                    incidencias_por_puesto[dept][puesto] = row['cantidad']
                return incidencias_por_puesto
            except Exception as e:
                logging.error(f"❌ Error obteniendo incidencias activas: {e}")
                return {}
            finally:
                conn.close()

    def agregar_comentario(self, incidencia_id: int, usuario: str, username: str, comentario: str) -> bool:
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO comentarios_incidencias (incidencia_id, usuario, username, comentario)
                    VALUES (?, ?, ?, ?)
                """, (incidencia_id, usuario, username, comentario))
                conn.commit()
                return True
            except Exception as e:
                logging.error(f"❌ Error agregando comentario: {e}")
                return False
            finally:
                conn.close()

    def get_tipos_incidencias(self) -> List[Dict]:
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT codigo, descripcion, categoria, prioridad FROM tipos_incidencias WHERE activo = 1")
                return cursor.fetchall()
            except Exception as e:
                logging.error(f"❌ Error obteniendo tipos: {e}")
                return []
            finally:
                conn.close()

    def get_estadisticas_generales(self, fecha_inicio: str = None, fecha_fin: str = None, departamento: str = None) -> Dict:
        with self._lock:
            conn = self._get_connection()
            try:
                where_clauses = []
                params = []
                if fecha_inicio:
                    where_clauses.append("fecha_creacion >= ?")
                    params.append(fecha_inicio)
                if fecha_fin:
                    where_clauses.append("fecha_creacion <= ?")
                    params.append(fecha_fin + ' 23:59:59')
                if departamento and departamento != 'todos':
                    where_clauses.append("departamento = ?")
                    params.append(departamento)
                
                where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
                
                query = f"""
                    SELECT 
                        COUNT(*) as total_incidencias,
                        SUM(CASE WHEN estado = 'pendiente' THEN 1 ELSE 0 END) as pendientes,
                        SUM(CASE WHEN estado = 'en_proceso' THEN 1 ELSE 0 END) as en_proceso,
                        SUM(CASE WHEN estado = 'resuelta' THEN 1 ELSE 0 END) as resueltas,
                        AVG(CASE WHEN estado = 'resuelta' THEN (julianday(fecha_resolucion) - julianday(fecha_creacion)) * 24 ELSE NULL END) as tiempo_promedio_resolucion_horas
                    FROM incidencias
                    {where_sql}
                """
                cursor = conn.cursor()
                cursor.execute(query, params)
                stats = cursor.fetchone()
                
                # Normalizar
                if stats:
                    for k in stats:
                        if stats[k] is None: stats[k] = 0
                    return stats
                return {'total_incidencias': 0, 'pendientes': 0, 'en_proceso': 0, 'resueltas': 0, 'tiempo_promedio_resolucion_horas': 0}
            except Exception as e:
                logging.error(f"❌ Error en estadísticas: {e}")
                return {'total_incidencias': 0, 'pendientes': 0, 'en_proceso': 0, 'resueltas': 0, 'tiempo_promedio_resolucion_horas': 0}
            finally:
                conn.close()
