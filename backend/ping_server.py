#!/usr/bin/env python3

"""
=============================================================================
SERVIDOR FLASK - SISTEMA DE CONTROL DE MESAS
=============================================================================
Sistema de monitorización en tiempo real con autenticación completa
Versión: 2.4 - CON MAPEO AUTOMÁTICO RET → PACK/VAS
=============================================================================
"""

from flask import Flask, request, jsonify, send_from_directory, session, redirect, Response
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect
import subprocess
import csv
import json
import os
from pathlib import Path
from wakepy import keep
from datetime import datetime
import logging
import random
from concurrent.futures import ThreadPoolExecutor
import threading
import socket
import time
from modulo_db_oracle.crud import Datos
try:
    from mysql_incidencias import MySQLIncidencias
except ImportError:
    class MySQLIncidencias: pass

try:
    from sqlite_incidencias import SQLiteIncidencias
except ImportError:
    class SQLiteIncidencias: pass

class MockMySQL:
    """Clase Mock para simulaciones sin base de datos real"""
    def __init__(self):
        self.connection = None
        self.incidencias = self._generar_incidencias_demo()
        logging.info("🛠️ MockMySQL inicializado (Modo Demo con datos enriquecidos)")
        
    def _generar_incidencias_demo(self):
        import random
        from datetime import datetime, timedelta
        data = []
        nombres = ["Marcos G.", "Lucia H.", "Roberto L.", "Elena S.", "Victor M.", "Raul B.", "Sonia T."]
        tecnicos = ["IT_ADMIN", "TECNICO_RUBEN", "TECNICO_ANA"]
        tipos = ["RFID_NO_LEE", "IMPRESORA_ZEBRA", "ITEM_NOT_FOUND", "PANTALLA", "PC_LENTO", "CONEXION_RED"]
        depts = ["packing", "return", "vas"]
        
        # 1. Crear 150 incidencias históricas para Analytics
        for i in range(1, 151):
            estado = random.choice(["resuelta", "resuelta", "resuelta", "resuelta", "resuelta", "pendiente", "en_proceso", "pausada"])
            dept = random.choice(depts)
            
            # Ajustar rango de puestos según departamento
            max_p = 60 if dept == "packing" else 20 if dept == "return" else 7
            puesto_num = random.randint(1, max_p)
            puesto_str = f"{dept.upper()}-{puesto_num}"
            
            tipo = random.choice(tipos)
            # Dias atrás: repartir en los últimos 30 días
            dias_atras = random.randint(0, 30)
            hora_flejado = datetime.now() - timedelta(days=dias_atras, hours=random.randint(1, 23), minutes=random.randint(0, 59))
            
            # Prioridad basada en tipo
            prioridad = "alta" if "RFID" in tipo or "IMPRESORA" in tipo else random.choice(["media", "baja"])
            
            minutos_total = random.randint(15, 180)
            minutos_pausa = random.randint(0, 30) if random.random() > 0.7 else 0
            
            inc = {
                'id': i,
                'departamento': dept,
                'puesto': puesto_num,  # ✅ USAR NÚMERO ENTERO EN LUGAR DE STRING
                'categoria': tipo,
                'prioridad': prioridad,
                'estado': estado,
                'fecha_creacion': hora_flejado.isoformat(),
                'reportado_por': random.choice(nombres),
                'descripcion': f"Fallo aleatorio en {tipo} - Simulación Demo",
                'comentarios_count': random.randint(0, 3),
                'minutos_total': minutos_total,
                'minutos_pausado': minutos_pausa,
                'minutos_efectivo': minutos_total - minutos_pausa,
                'notas_resolucion': "Problema resuelto tras verificación de hardware." if estado == "resuelta" else ""
            }
            
            if estado == "resuelta":
                inc['fecha_resolucion'] = (hora_flejado + timedelta(minutes=minutos_total)).isoformat()
                inc['resuelto_por'] = random.choice(tecnicos)
            elif estado == "pausada":
                inc['fecha_pausa'] = (datetime.now() - timedelta(minutes=10)).isoformat()
                inc['motivo_pausa'] = "Esperando piezas"
                
            data.append(inc)
            
        # 2. Asegurar ~5% de puestos con incidencias ACTIVAS (Dashboard)
        # 5% de ~87 puestos = 4-5 puestos.
        puestos_activos = [
            ("packing", 5, "RFID_NO_LEE"),
            ("packing", 14, "IMPRESORA_ZEBRA"),
            ("return", 3, "PANTALLA"),
            ("vas", 2, "PC_LENTO")
        ]
        
        for dept, p, tipo in puestos_activos:
            # Eliminar previas de ese puesto para no saturar
            data = [x for x in data if not (x['departamento'] == dept and x['puesto'] == p and x['estado'] != 'resuelta')]
            
            data.append({
                'id': len(data) + 1,
                'departamento': dept,
                'puesto': p,  # ✅ AHORA ES NÚMERO ENTERO, NO STRING
                'categoria': tipo,
                'prioridad': 'alta',
                'estado': 'en_proceso',
                'fecha_creacion': (datetime.now() - timedelta(minutes=45)).isoformat(),
                'reportado_por': random.choice(nombres),
                'descripcion': f"Incidencia crítica activa para visualización en tablero.",
                'comentarios_count': 1,
                'minutos_total': 45,
                'minutos_pausado': 0,
                'minutos_efectivo': 45
            })
            
        return data

    def __getattr__(self, name):
        def mock_method(*args, **kwargs):
            logging.warning(f"🛠️ MODO DEMO: Llamada a '{name}' (Mock)")
            # Retornar lista vacía por defecto para evitar errores de len() o iteración
            return []
        return mock_method

    def is_connected(self): return True
    def close(self): pass
    
    def get_incidencias_activas_por_puesto(self):
        res = {}
        for inc in self.incidencias:
            if inc['estado'] in ['pendiente', 'en_proceso', 'pausada']:
                d = inc['departamento']
                p_str = inc['puesto'].split('-')[1]
                try:
                    p = int(p_str)
                except:
                    continue
                if d not in res: res[d] = {}
                res[d][p] = res[d].get(p, 0) + 1
        return res

    def get_todas_incidencias(self): return self.incidencias
    
    def get_todas_zebra(self, activas_solo=True):
        # Simular una lista de Zebras para el worker de chequeo
        res = []
        for i in range(1, 11):
            res.append({
                'id': i,
                'departamento': 'packing',
                'puesto': i,
                'ip': f'192.168.10.{100+i}',
                'modelo': 'ZD421',
                'custom_locked': False
            })
        return res

    def get_zebras_bloqueadas(self): return []
    def get_zebras_configuracion(self, departamento=None, puesto_desde=None, puesto_hasta=None): return []

    def exportar_incidencias_csv(self, fecha_inicio=None, fecha_fin=None, departamento=None):
        res = self.incidencias
        if departamento and departamento != 'todos':
            res = [i for i in res if i['departamento'] == departamento]
        return res

    def get_tipos_incidencias(self):
        return [
            {'id': 1, 'codigo': 'RFID_NO_LEE', 'nombre': 'RFID No Lee', 'prioridad_default': 'alta'},
            {'id': 2, 'codigo': 'ITEM_NOT_FOUND', 'nombre': 'Item No Encontrado', 'prioridad_default': 'media'},
            {'id': 3, 'codigo': 'IMPRESORA_ZEBRA', 'nombre': 'Problema Impresora', 'prioridad_default': 'media'},
            {'id': 4, 'codigo': 'PC_LENTO', 'nombre': 'Ordenador Lento', 'prioridad_default': 'baja'},
            {'id': 5, 'codigo': 'PANTALLA', 'nombre': 'Problema Pantalla', 'prioridad_default': 'media'},
            {'id': 6, 'codigo': 'CONEXION_RED', 'nombre': 'Error de Red', 'prioridad_default': 'alta'},
            {'id': 7, 'codigo': 'OTRO', 'nombre': 'Otro Problema', 'prioridad_default': 'media'}
        ]
    
    def get_estadisticas_generales(self):
        total = len(self.incidencias)
        resueltas = sum(1 for i in self.incidencias if i['estado'] == 'resuelta')
        pendientes = sum(1 for i in self.incidencias if i['estado'] == 'pendiente')
        en_proceso = sum(1 for i in self.incidencias if i['estado'] == 'en_proceso')
        return {
            'total_incidencias': total,
            'incidencias_resueltas': resueltas,
            'incidencias_pendientes': pendientes,
            'incidencias_en_proceso': en_proceso,
            'sla_cumplido': 92.4
        }
    
    def get_sla_compliance(self, sla_horas=4, fecha_inicio=None, fecha_fin=None):
        return {
            'cumple': sum(1 for i in self.incidencias if i['estado'] == 'resuelta' and i['minutos_total'] <= sla_horas*60),
            'no_cumple': sum(1 for i in self.incidencias if i['estado'] == 'resuelta' and i['minutos_total'] > sla_horas*60),
            'total_resueltas': sum(1 for i in self.incidencias if i['estado'] == 'resuelta'),
            'porcentaje_cumplimiento': 92.4
        }
        
    def get_tiempos_por_motivo_pausa(self, fecha_inicio=None, fecha_fin=None):
        return [
            {'motivo': 'Esperando IT', 'total_minutos': 450, 'cantidad': 12},
            {'motivo': 'Esperando Repuesto', 'total_minutos': 1200, 'cantidad': 5},
            {'motivo': 'Operario ausente', 'total_minutos': 300, 'cantidad': 8},
            {'motivo': 'Cambio de turno', 'total_minutos': 150, 'cantidad': 10}
        ]
        
    def get_tiempos_efectivo_vs_total(self, dias=30, fecha_inicio=None, fecha_fin=None):
        from datetime import datetime, timedelta
        labels = [(datetime.now() - timedelta(days=i)).strftime('%d/%m') for i in range(7)][::-1]
        return {
            'labels': labels,
            'tiempo_total': [random.randint(400, 600) for _ in range(7)],
            'tiempo_efectivo': [random.randint(300, 400) for _ in range(7)]
        }
        
    def get_eficiencia_tecnicos(self, fecha_inicio=None, fecha_fin=None):
        return [
            {'tecnico': 'IT_ADMIN', 'incidencias_resueltas': 45, 'tiempo_promedio': 24.5},
            {'tecnico': 'TECNICO_RUBEN', 'incidencias_resueltas': 38, 'tiempo_promedio': 28.2},
            {'tecnico': 'TECNICO_ANA', 'incidencias_resueltas': 32, 'tiempo_promedio': 22.1}
        ]
    
    def get_estadisticas_avanzadas(self, fecha_inicio=None, fecha_fin=None, departamento=None):
        return self.get_estadisticas_generales()

from functools import wraps
from utils.validators import (
    validate_username, validate_password, validate_incidencia_data,
    validate_departamento, validate_puesto, validate_range, sanitize_string
)

# ✅ Cargar configuración desde .env
from config import FlaskConfig, ServiceConfig

import sys
import os

# Determinar directorios según si es ejecutable o script
if getattr(sys, 'frozen', False):
    # Si es ejecutable empaquetado
    base_dir = Path(sys._MEIPASS)
    exe_dir = Path(sys.executable).parent
    # El frontend está empaquetado
    frontend_dir = base_dir / 'frontend'
    # La config y logs están fuera, junto al exe
    config_dir = exe_dir / 'config'
    log_dir = exe_dir  # Logs en la carpeta del exe
else:
    # Si es script normal
    base_dir = Path(__file__).resolve().parent
    exe_dir = base_dir
    frontend_dir = base_dir.parent / 'frontend'
    config_dir = base_dir.parent / 'config'
    log_dir = base_dir

assets_dir = frontend_dir / 'assets'

app = Flask(__name__, 
            static_folder=str(assets_dir),
            static_url_path='/assets')

# ✅ Configurar logging con ruta dinámica antes de nada
log_file = log_dir / 'ping_server.log'
from logging.handlers import RotatingFileHandler
file_handler = RotatingFileHandler(
    str(log_file),
    maxBytes=10*1024*1024,
    backupCount=5,
    encoding='utf-8'
)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[file_handler, logging.StreamHandler(sys.stdout)]
)

# ✅ Usar configuración desde .env
flask_config = FlaskConfig.get_config()
app.secret_key = flask_config['secret_key']
# 🔴 Desactivar CSRF globalmente (temporal)
app.config['WTF_CSRF_ENABLED'] = False
CORS(app, supports_credentials=True)

# ✅ Configurar CSRF Protection
csrf = CSRFProtect(app)

# Eximir las APIs de la protección CSRF ya que se manejan con CORS y cookies seguras
@app.before_request
def exempt_api_csrf():
    if request.path.startswith('/api/'):
        # Esto desactiva CSRF para esta petición
        setattr(request, '_csrf_exempt', True)

# ✅ Configurar Rate Limiting
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per hour", "50 per minute"],
    storage_uri="memory://"
)

# =============================================================================
# 🆕 FUNCIÓN DE MAPEO RET → PACK/VAS
# =============================================================================
def mapear_ret_a_pack_vas(usuario_data):
    """
    Mapea los puestos RET según su número:
    - RET-25 a RET-60 → PACK-25 a PACK-60
    - RET-61 a RET-65 → VAS-1 a VAS-5
    
    Args:
        usuario_data (dict): Diccionario con datos del usuario
            {
                'station': 'RET-45',
                'user': 'JUAN PEREZ',
                'hora': '14:30'
            }
    
    Returns:
        tuple: (usuario_data_modificado, fue_mapeado)
    """
    # ✅ CONVERTIR DE JAVA A PYTHON PRIMERO
    station = convert_java_to_python(usuario_data.get('station', ''))
    
    # Validar que station sea un string
    if not isinstance(station, str) or not station:
        return usuario_data, False
    
    # Si NO es un puesto RET, retornar sin modificar
    if not station.startswith('RET-'):
        return usuario_data, False
    
    try:
        # Extraer número del puesto (ej: "RET-25" → 25)
        numero_ret = int(station.split('-')[1])
        
        # ✅ Mapeo RET-25 a RET-60 → PACK-25 a PACK-60
        if 25 <= numero_ret <= 60:
            usuario_data_mapeado = usuario_data.copy()
            usuario_data_mapeado['station'] = f'PACK-{numero_ret}'
            # ✅ AÑADIR INFORMACIÓN DE MAPEO PARA EL FRONTEND
            usuario_data_mapeado['wasRetMapped'] = True
            usuario_data_mapeado['originalStation'] = f'RET-{numero_ret}'
            usuario_nombre = convert_java_to_python(usuario_data.get('user', 'Usuario'))
            logging.info(f"🔄 Mapeado: RET-{numero_ret} → PACK-{numero_ret} ({usuario_nombre})")
            return usuario_data_mapeado, True
        
        # ✅ Mapeo RET-61 a RET-65 → VAS-1 a VAS-5
        elif 61 <= numero_ret <= 65:
            numero_vas = numero_ret - 60  # RET-61→VAS-1, RET-62→VAS-2, etc.
            usuario_data_mapeado = usuario_data.copy()
            usuario_data_mapeado['station'] = f'VAS-{numero_vas}'
            # ✅ AÑADIR INFORMACIÓN DE MAPEO PARA EL FRONTEND
            usuario_data_mapeado['wasRetMapped'] = True
            usuario_data_mapeado['originalStation'] = f'RET-{numero_ret}'
            usuario_nombre = convert_java_to_python(usuario_data.get('user', 'Usuario'))
            logging.info(f"🔄 Mapeado: RET-{numero_ret} → VAS-{numero_vas} ({usuario_nombre})")
            return usuario_data_mapeado, True
        
    except (ValueError, IndexError, AttributeError) as e:
        logging.warning(f"⚠️ Error en mapeo para station={station}: {str(e)}")
        pass
    
    # Si no entra en ningún rango, retornar sin modificar
    return usuario_data, False


# El logging ya ha sido configurado arriba para asegurar que captura el inicio del sistema

# =============================================================================
# CONFIGURACIÓN GLOBAL
# =============================================================================
# ✅ Credenciales desde .env (ya NO están hardcodeadas)
TEAMVIEWER_PASSWORD = ServiceConfig.get_teamviewer_password()
ssh_config = ServiceConfig.get_ssh_config()
RFID_SSH_PASSWORD = ssh_config['password']
RFID_SSH_USER = ssh_config['user']

machines_config = {'packing': {}, 'return': {}, 'vas': {}}
rfid_config = {'packing': {}, 'return': {}, 'vas': {}}
zebra_config = {'packing': {}, 'return': {}, 'vas': {}}

active_users_cache = {}
# ✅ Cargar configuración desde .env
cache_config = ServiceConfig.get_cache_config()
user_cache_timeout = cache_config['user_cache_timeout']
usuarios_sistema = {}
tipos_incidencias = []
mysql_db = None

# ✅ ThreadPoolExecutor con configuración desde .env
thread_pool_config = ServiceConfig.get_thread_pool_config()
executor = ThreadPoolExecutor(max_workers=thread_pool_config['max_workers'])

# Variables de control para Oracle
oracle_datos = None
oracle_lock = threading.Lock()
last_oracle_fail_time = 0
ORACLE_COOLDOWN_SECONDS = 60  # No reintentar en 1 minuto si falla

# =============================================================================
# FUNCIONES DE AUTENTICACIÓN (mantener las existentes)
# =============================================================================
def load_users_from_mysql():
    """Carga usuarios desde MySQL"""
    global usuarios_sistema
    usuarios_sistema = {}
    
    if not mysql_db:
        logging.error("❌ MySQL no conectado")
        return False
    
    try:
        usuarios_lista = mysql_db.get_todos_usuarios()
        
        for user in usuarios_lista:
            username = user['username']
            usuarios_sistema[username] = {
                'username': username,
                'password': user.get('password', ''),  # No lo usaremos directamente
                'nombre_completo': user['nombre_completo'],
                'rol': user['rol'],
                'departamento': user['departamento'],
                'activo': user['activo']
            }
        
        logging.info(f"✅ Cargados {len(usuarios_sistema)} usuarios desde MySQL")
        return True
        
    except Exception as e:
        logging.error(f"❌ Error cargando usuarios desde MySQL: {str(e)}")
        return False
# ✅ Bandera global para Modo Demo
IS_DEMO_MODE = False

def load_incidencias_from_db():
    """Inicializa conexión a la base de datos (MySQL o SQLite) o activa Modo Demo si falla"""
    global mysql_db, IS_DEMO_MODE
    
    # 1. Intentar MySQL
    try:
        mysql_db = MySQLIncidencias()
        if hasattr(mysql_db, 'is_connected') and mysql_db.is_connected():
            logging.info("✅ Conexión MySQL inicializada")
            IS_DEMO_MODE = False
            return True
    except Exception as e:
        logging.warning(f"⚠️ Error MySQL: {str(e)}")

    # 2. Intentar SQLite (Local)
    try:
        logging.info("🔄 Intentando conectar a SQLite...")
        mysql_db = SQLiteIncidencias()
        # SQLiteIncidencias se inicializa al instanciar, si no hay error asumimos éxito
        logging.info("✅ Conexión SQLite inicializada")
        IS_DEMO_MODE = False
        return True
    except Exception as e:
        logging.error(f"❌ Error SQLite: {str(e)}")

    # 3. Fallback a Modo Demo
    logging.warning("⚠️ No hay base de datos disponible. ACTIVANDO MODO DEMO.")
    mysql_db = MockMySQL()
    IS_DEMO_MODE = True
    return False


def load_tipos_incidencias():
    """Carga tipos de incidencias desde MySQL"""
    global tipos_incidencias
    try:
        if mysql_db is None:
            logging.warning("⚠️ mysql_db no inicializado, usando fallback CSV")
            return load_tipos_incidencias_from_file()
        
        tipos_incidencias = mysql_db.get_tipos_incidencias()
        logging.info(f"✅ Cargados {len(tipos_incidencias)} tipos de incidencias desde BD")
        return True
    except Exception as e:
        logging.error(f"❌ Error cargando tipos de incidencias: {str(e)}")
        # Fallback: cargar desde archivo CSV
        return load_tipos_incidencias_from_file()

def load_tipos_incidencias_from_file():
    """Fallback: cargar tipos desde archivo CSV"""
    global tipos_incidencias
    tipos_incidencias = []
    filename = config_dir / 'tipos_incidencias.csv'
    if not filename.exists():
        logging.warning(f"Archivo {filename} no encontrado")
        return False
    try:
        with open(filename, 'r', encoding='utf-8') as file:
            first_line = file.readline().strip()
            file.seek(0)
            separator = '\t' if '\t' in first_line else ','
            reader = csv.DictReader(file, delimiter=separator)
            for row in reader:
                tipos_incidencias.append({
                    'codigo': row['codigo'].strip(),
                    'descripcion': row['descripcion'].strip(),
                    'categoria': row['categoria'].strip(),
                    'prioridad': row['prioridad'].strip()
                })
        logging.info(f"✅ Cargados {len(tipos_incidencias)} tipos de incidencias desde CSV (fallback)")
        return True
    except Exception as e:
        logging.error(f"❌ Error cargando tipos de incidencias desde CSV: {str(e)}")
        return False



def login_required(f):
    """Decorador para proteger endpoints que requieren autenticación"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return jsonify({
                'success': False,
                'error': 'No autorizado',
                'authenticated': False
            }), 401
        return f(*args, **kwargs)
    return decorated_function

# =============================================================================
# FUNCIÓN DE CONVERSIÓN JAVA A PYTHON
# =============================================================================
def convert_java_to_python(obj):
    """Convierte objetos Java a tipos nativos de Python"""
    if obj is None:
        return None
    if hasattr(obj, '__class__'):
        type_str = str(type(obj))
        if 'java.lang.String' in type_str or 'java.lang' in type_str:
            return str(obj)
    if isinstance(obj, list):
        return [convert_java_to_python(item) for item in obj]
    if isinstance(obj, dict):
        return {key: convert_java_to_python(value) for key, value in obj.items()}
    if isinstance(obj, (str, int, float, bool)):
        return obj
    try:
        return str(obj)
    except:
        return None

# =============================================================================
# FUNCIONES DE CARGA DE CONFIGURACIÓN
# =============================================================================
def load_machines_from_mysql():
    """Carga la configuración de máquinas desde MySQL"""
    global machines_config
    machines_config = {}
    
    if not mysql_db:
        logging.error("❌ MySQL no conectado, no se pueden cargar mesas")
        return False
    
    try:
        mesas = mysql_db.get_todas_mesas(activas_solo=True)
        
        if not mesas or len(mesas) == 0:
            logging.warning("⚠️  No hay mesas activas en la base de datos")
            return False
        
        for mesa in mesas:
            dept = mesa['departamento'].lower()
            puesto = int(mesa['puesto'])
            ip = mesa['ip']
            
            if dept not in machines_config:
                machines_config[dept] = {}
            
            machines_config[dept][puesto] = ip
        
        total_machines = sum(len(puestos) for puestos in machines_config.values())
        logging.info(f"✅ Cargadas {total_machines} máquinas desde MySQL")
        
        # Mostrar resumen por departamento
        for dept, puestos in machines_config.items():
            logging.info(f"   • {dept}: {len(puestos)} mesas")
        
        return True
        
    except Exception as e:
        logging.error(f"❌ Error cargando máquinas desde MySQL: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())
        return False

def load_rfid_from_mysql():
    """Carga la configuración de dispositivos RFID desde MySQL"""
    global rfid_config
    rfid_config = {}
    
    if not mysql_db:
        logging.warning("⚠️  MySQL no conectado, RFID no estará disponible")
        return False
    
    try:
        dispositivos = mysql_db.get_todos_rfid(activos_solo=True)
        
        if not dispositivos or len(dispositivos) == 0:
            logging.info("ℹ️  No hay dispositivos RFID activos en la base de datos")
            return False
        
        for dispositivo in dispositivos:
            dept = dispositivo['departamento'].lower()
            puesto = int(dispositivo['puesto'])
            ip = dispositivo['ip']
            
            if dept not in rfid_config:
                rfid_config[dept] = {}
            
            rfid_config[dept][puesto] = ip
        
        total_rfid = sum(len(puestos) for puestos in rfid_config.values())
        logging.info(f"✅ Cargados {total_rfid} dispositivos RFID desde MySQL")
        
        # Mostrar resumen por departamento
        for dept, puestos in rfid_config.items():
            logging.info(f"   • {dept}: {len(puestos)} dispositivos RFID")
        
        return True
        
    except Exception as e:
        logging.error(f"❌ Error cargando RFID desde MySQL: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())
        return False

def load_zebra_from_mysql():
    """Carga la configuración de impresoras Zebra desde MySQL"""
    global zebra_config
    zebra_config = {}
    
    if not mysql_db:
        logging.warning("⚠️  MySQL no conectado, impresoras Zebra no estarán disponibles")
        return False
    
    try:
        impresoras = mysql_db.get_todas_zebra(activas_solo=True)
        
        if not impresoras or len(impresoras) == 0:
            logging.info("ℹ️  No hay impresoras Zebra activas en la base de datos")
            return False
        
        for impresora in impresoras:
            dept = impresora['departamento'].lower()
            puesto = int(impresora['puesto'])
            
            if dept not in zebra_config:
                zebra_config[dept] = {}
            
            zebra_config[dept][puesto] = {
                'ip': impresora['ip'],
                'puerto': impresora.get('puerto', 9100),
                'modelo': impresora.get('modelo', 'ZD420/ZD421'),
                'darkness_default': impresora.get('darkness_default', 15),
                'darkness_custom': impresora.get('darkness_custom'),
                'speed_default': impresora.get('speed_default', 4),
                'top_default': impresora.get('top_default', 0),
                'tear_off_default': impresora.get('tear_off_default', 0),
                'left_position': impresora.get('left_position', 0),
                'custom_locked': impresora.get('custom_locked', False)
            }
        
        total_zebra = sum(len(puestos) for puestos in zebra_config.values())
        logging.info(f"✅ Cargadas {total_zebra} impresoras Zebra desde MySQL")
        
        # Mostrar resumen por departamento
        for dept, puestos in zebra_config.items():
            logging.info(f"   • {dept}: {len(puestos)} impresoras Zebra")
        
        return True
        
    except Exception as e:
        logging.error(f"❌ Error cargando impresoras Zebra desde MySQL: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())
        return False

# =============================================================================
# FUNCIONES DE RED Y CONECTIVIDAD
# =============================================================================
def ejecutar_ssh_reboot(ip, password=RFID_SSH_PASSWORD):
    """Reinicia el sistema RFID mediante SSH"""
    try:
        import paramiko
        # Timeout fijo de 10 segundos
        ssh_timeout = 10
        
        logging.info(f"🔄 Intentando reiniciar RFID en {ip} (timeout: {ssh_timeout}s)")
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            ip,
            username=RFID_SSH_USER,
            password=password,
            timeout=ssh_timeout,
            look_for_keys=False
        )
        # Agregar timeout al comando también
        stdin, stdout, stderr = client.exec_command('reboot', timeout=ssh_timeout)
        client.close()
        logging.info(f"✅ Reboot RFID enviado exitosamente a {ip}")
        return True, f"Reboot enviado a {ip}"
    except ImportError:
        error_msg = "Librería paramiko no instalada. Ejecuta: pip install paramiko"
        logging.error(f"❌ {error_msg}")
        return False, error_msg
    except Exception as e:
        # NO loguear la contraseña en el error
        error_msg = f"Error al reiniciar RFID en {ip}: {str(e)}"
        logging.error(f"❌ {error_msg}")
        return False, error_msg

def ping_ip(ip, timeout=3):
    """Verifica la conectividad de red con una IP mediante ping"""
    global IS_DEMO_MODE
    if IS_DEMO_MODE:
        # Hacemos que solo un par de pings fallen para el color ROJO
        try:
            # Si termina en .0 o es múltiplo de 30, simulamos caída (Rojo)
            last_part = int(ip.split('.')[-1])
            if last_part % 30 == 0: 
                logging.debug(f"🔴 DEMO: IP {ip} marcada como OFFLINE (último octeto {last_part} % 30 == 0)")
                return False, 0.0, "Timeout (Simulado)"
        except Exception as e:
            logging.warning(f"⚠️ Error procesando IP {ip}: {e}")
            pass
        
        # El resto son ONLINE (Verde si no hay usuario, Azul si hay usuario)
        logging.debug(f"🟢 DEMO: IP {ip} marcada como ONLINE")
        return True, random.uniform(0.1, 0.8), None
        
    try:
        cmd = ["ping", "-n", "1", ip]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 2)
        output = result.stdout.lower()
        fail_messages = [
            "host de destino inaccesible",
            "tiempo de espera agotado",
            "request timed out",
            "destination host unreachable",
            "general failure"
        ]
        has_failure = any(msg in output for msg in fail_messages)
        success = result.returncode == 0 and not has_failure
        return success, 1.0 if success else 0.0, None if success else "Ping failed"
    except Exception as e:
        return False, 0.0, str(e)

def get_local_ip():
    """Obtiene la IP local del servidor"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        return "127.0.0.1"

# =============================================================================
# 🆕 FUNCIÓN MODIFICADA - ACTUALIZAR USUARIOS ACTIVOS CON MAPEO
# =============================================================================

# Instancia global de Oracle para evitar crear conexiones repetidamente
oracle_datos = None

oracle_lock = threading.Lock()

def get_oracle_connection():
    """
    Obtiene la instancia global de conexión Oracle, creándola si no existe.
    Incluye reconexión automática si la conexión se perdió.
    Implementa un cooldown para evitar bloqueos por reintentos constantes.
    """
    global oracle_datos, IS_DEMO_MODE, last_oracle_fail_time
    
    if IS_DEMO_MODE:
        return None
        
    current_time = time.time()
    if current_time - last_oracle_fail_time < ORACLE_COOLDOWN_SECONDS:
        # logging.debug(f"⏳ Oracle en cooldown ({int(ORACLE_COOLDOWN_SECONDS - (current_time - last_oracle_fail_time))}s restantes)")
        return None
        
    with oracle_lock:
        try:
            if oracle_datos is None:
                logging.info("🔌 Creando nueva conexión Oracle...")
                oracle_datos = Datos()
                if not oracle_datos.is_connected():
                    last_oracle_fail_time = time.time()
                    oracle_datos = None
                    return None
            elif not oracle_datos.is_connected():
                logging.warning("⚠️ Conexión Oracle perdida, reconectando...")
                if not oracle_datos.reconnect():
                    logging.error("❌ No se pudo reconectar a Oracle, esperando cooldown...")
                    last_oracle_fail_time = time.time()
                    oracle_datos = None
                    return None
            return oracle_datos
        except Exception as e:
            logging.error(f"❌ Error obteniendo conexión Oracle: {e}")
            last_oracle_fail_time = time.time()
            oracle_datos = None
            return None

def update_active_users_from_db():
    """
    Actualiza el cache de usuarios activos consultando Oracle Database
    Si Oracle no está disponible, preserva el caché existente (del arranque)
    """
    global active_users_cache, IS_DEMO_MODE
    
    if IS_DEMO_MODE:
        # En modo demo, no actualizamos desde DB
        return
    
    # ✅ Si ya tenemos caché del arranque, no tocar Oracle
    # Los usuarios se generaron al iniciar el servidor
    if active_users_cache:
        return
        
    try:
        datos = get_oracle_connection()
        if datos is None:
            # Solo cargar demo si el caché está vacío
            if not active_users_cache:
                load_demo_users_cache()
            return
        
        # Obtener usuarios CON NOMBRE (include_nombre=True por defecto)
        usuarios_packing = datos.get_user_time_packing(include_nombre=True)
        usuarios_return = datos.get_user_time_return(include_nombre=True)
        usuarios_vas = datos.get_user_time_vas(include_nombre=True)
        
        todos_usuarios = []
        
        # ✅ Agregar usuarios de PACKING sin modificar
        if usuarios_packing and len(usuarios_packing) > 0:
            todos_usuarios.extend(usuarios_packing)
            logging.info(f"📦 Packing: {len(usuarios_packing)} usuarios directos")
        
        # ✅ PROCESAR USUARIOS DE RETURN CON MAPEO
        if usuarios_return and len(usuarios_return) > 0:
            usuarios_return_normales = []
            usuarios_mapeados_a_pack = []
            usuarios_mapeados_a_vas = []
            
            for user_data in usuarios_return:
                # Intentar mapear a PACK (25-60) o VAS (61-65)
                mapped_data, fue_mapeado = mapear_ret_a_pack_vas(user_data)
                
                if fue_mapeado:
                    # Usuario mapeado
                    if mapped_data['station'].startswith('PACK-'):
                        usuarios_mapeados_a_pack.append(mapped_data)
                    elif mapped_data['station'].startswith('VAS-'):
                        usuarios_mapeados_a_vas.append(mapped_data)
                    todos_usuarios.append(mapped_data)
                else:
                    # Return normal (1-24)
                    usuarios_return_normales.append(user_data)
                    todos_usuarios.append(user_data)
            
            logging.info(f"🔄 Return procesado: {len(usuarios_return_normales)} normales, "
                        f"{len(usuarios_mapeados_a_pack)} → PACK, "
                        f"{len(usuarios_mapeados_a_vas)} → VAS")
        
        # ✅ Agregar usuarios de VAS sin modificar
        if usuarios_vas and len(usuarios_vas) > 0:
            todos_usuarios.extend(usuarios_vas)
            logging.info(f"🏷️ VAS: {len(usuarios_vas)} usuarios directos")
        
        # ✅ Construir cache con todas las posibles claves (INCLUYE NOMBRE)
        if len(todos_usuarios) > 0:
            active_users_cache = {}
            for user_data in todos_usuarios:
                station = convert_java_to_python(user_data.get('station', ''))
                usuario = convert_java_to_python(user_data.get('user', ''))
                nombre = convert_java_to_python(user_data.get('nombre', ''))
                hora = convert_java_to_python(user_data.get('hora', ''))
                
                if '-' in station:
                    parts = station.split('-')
                    dept_prefix = parts[0].upper()
                    puesto_num_raw = parts[1]
                    puesto_num = str(int(puesto_num_raw))
                    
                    dept_map = {
                        'PACK': 'packing',
                        'RET': 'return',
                        'VAS': 'vas'
                    }
                    dept = dept_map.get(dept_prefix, dept_prefix.lower())
                    station_normalized = f"{dept_prefix}-{puesto_num}"
                    
                    # ✅ INCLUYE NOMBRE DEL OPERARIO Y INFO DE MAPEO
                    was_ret_mapped = user_data.get('wasRetMapped', False)
                    original_station = user_data.get('originalStation', '')
                    
                    user_info = {
                        'usuario': usuario,
                        'nombre': nombre,
                        'station': station_normalized,
                        'hora': hora,
                        'wasRetMapped': was_ret_mapped,  # ✅ NUEVO: Indica si viene de RET
                        'originalStation': original_station  # ✅ NUEVO: Station original (ej: RET-56)
                    }
                    
                    # Guardar con todas las posibles claves para búsqueda
                    key1 = f"{dept}-{puesto_num}"
                    active_users_cache[key1] = user_info
                    key2 = f"{dept}-{station_normalized}"
                    active_users_cache[key2] = user_info
                    key3 = f"{dept}-{puesto_num_raw}"
                    active_users_cache[key3] = user_info
                    key4 = f"{dept}-{station}"
                    active_users_cache[key4] = user_info
                
                # ✅ NUEVO: Manejar estaciones VAS con punto (VAS.01, VAS.02, etc)
                elif '.' in station:
                    parts = station.split('.')
                    dept_prefix = parts[0].upper()
                    puesto_num_raw = parts[1]
                    # Remover ceros a la izquierda: "02" -> "2"
                    puesto_num = str(int(puesto_num_raw))
                    
                    dept_map = {
                        'PACK': 'packing',
                        'RET': 'return',
                        'VAS': 'vas'
                    }
                    dept = dept_map.get(dept_prefix, dept_prefix.lower())
                    # Normalizar a formato con guión para consistencia
                    station_normalized = f"{dept_prefix}-{puesto_num}"
                    
                    user_info = {
                        'usuario': usuario,
                        'nombre': nombre,
                        'station': station_normalized,
                        'hora': hora
                    }
                    
                    # Guardar con múltiples claves para búsqueda flexible
                    key1 = f"{dept}-{puesto_num}"
                    active_users_cache[key1] = user_info
                    key2 = f"{dept}-{station_normalized}"
                    active_users_cache[key2] = user_info
                    key3 = f"{dept}-{puesto_num_raw}"
                    active_users_cache[key3] = user_info
                    # También clave con punto original
                    key5 = f"{dept}-{station}"
                    active_users_cache[key5] = user_info
            
            usuarios_unicos = len(todos_usuarios)
            logging.info(f"✅ Cache actualizado: {usuarios_unicos} usuarios activos totales")
        else:
            active_users_cache = {}
            logging.info("ℹ️ No hay usuarios activos en este momento")
        
        # NO cerramos la conexión aquí - la mantenemos abierta para reutilizarla
        
    except Exception as e:
        logging.error(f"❌ Error actualizando usuarios activos: {str(e)}")
        # Solo cargar demo si el caché está vacío
        if not active_users_cache:
            load_demo_users_cache()

def load_demo_users_cache():
    """Carga usuarios de prueba en el cache para demostraciones sin base de datos"""
    global active_users_cache
    logging.info("🎮 Cargando usuarios en MODO DEMO...")
    demo_users = [
        {'dept': 'packing', 'puesto': 4, 'user': 'USER001', 'nombre': 'Juan Pérez', 'hora': '08:30'},
        {'dept': 'packing', 'puesto': 5, 'user': 'USER002', 'nombre': 'Ana García', 'hora': '09:15'},
        {'dept': 'return', 'puesto': 1, 'user': 'USER003', 'nombre': 'Luis Rodríguez', 'hora': '08:00'},
        {'dept': 'vas', 'puesto': 1, 'user': 'USER004', 'nombre': 'María López', 'hora': '10:00'},
    ]
    for u in demo_users:
        key = f"{u['dept']}-{u['puesto']}"
        active_users_cache[key] = {
            'usuario': u['user'],
            'nombre': u['nombre'],
            'station': f"{u['dept'].upper()}-{u['puesto']}",
            'hora': u['hora']
        }



# =============================================================================
# ENDPOINTS DE AUTENTICACIÓN (mantener existentes)
# =============================================================================
@app.route('/login')
def serve_login():
    """Servir página de login"""
    try:
        login_html = frontend_dir / 'login.html'
        with open(login_html, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return f"Login page not found at {login_html}", 404
    
@app.route('/login.html')
def serve_login_html():
    """Ruta alternativa para login.html"""
    return serve_login()   

@app.route('/api/login', methods=['POST'])
@limiter.limit("5 per minute")  # Rate limiting: máximo 5 intentos por minuto
def login():
    """Endpoint de login con verificación MySQL o Modo Demo"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'Datos de entrada inválidos'
            }), 400
        
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        
        # Validar entrada
        username_valid, username_error = validate_username(username)
        if not username_valid:
            return jsonify({
                'success': False,
                'error': username_error
            }), 400
        
        password_valid, password_error = validate_password(password)
        if not password_valid:
            return jsonify({
                'success': False,
                'error': password_error
            }), 400
        
        user = None
        
        # ✅ MODO DEMO: Verificar contra usuarios_sistema en memoria
        if username in usuarios_sistema:
            user_data = usuarios_sistema[username]
            if user_data.get('password') == password:
                user = {
                    'username': user_data['username'],
                    'nombre_completo': user_data.get('nombre_completo', username),
                    'rol': user_data.get('rol', 'TECNICO'),
                    'departamento': user_data.get('departamento', 'IT'),
                    'activo': user_data.get('activo', 1)
                }
                logging.info(f"✅ Login MODO DEMO: {username}")
        
        # ✅ Si no se encontró en modo demo, intentar MySQL
        if not user and mysql_db:
            try:
                user = mysql_db.verificar_credenciales(username, password)
            except:
                user = None
        
        if not user:
            logging.warning(f"❌ Login fallido para usuario: {username}")
            return jsonify({
                'success': False,
                'error': 'Usuario o contraseña incorrectos'
            }), 401
        
        if not user.get('activo', True):
            logging.warning(f"❌ Usuario desactivado: {username}")
            return jsonify({
                'success': False,
                'error': 'Usuario desactivado'
            }), 401
        
        # ✅ CREAR SESIÓN
        session['user'] = {
            'username': user['username'],
            'nombre_completo': user['nombre_completo'],
            'rol': user['rol'],
            'departamento': user['departamento']
        }
        
        # ✅ REGISTRAR SESIÓN EN BD (si está disponible)
        try:
            if mysql_db:
                ip_address = request.remote_addr
                mysql_db.registrar_sesion(username, ip_address)
        except:
            pass  # Ignorar errores de registro en modo demo
        
        logging.info(f"✅ Login exitoso: {username} ({user['nombre_completo']}) - Rol: {user['rol']}")
        
        return jsonify({
            'success': True,
            'user': session['user'],
            'redirect': '/'
        })
        
    except Exception as e:
        logging.error(f"❌ Error en login: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': f'Error interno del servidor: {str(e)}'
        }), 500


@app.route('/api/logout', methods=['POST'])
def logout():
    """Endpoint de logout"""
    username = session.get('user', {}).get('username', 'Unknown')
    session.clear()
    logging.info(f"👋 Logout: {username}")
    return jsonify({'success': True})

@app.route('/api/session', methods=['GET'])
def check_session():
    """Verificar si hay sesión activa"""
    if 'user' in session:
        return jsonify({
            'authenticated': True,
            'user': session['user']
        })
    return jsonify({
        'authenticated': False
    })

# =============================================================================
# ENDPOINTS API - ARCHIVOS ESTÁTICOS
# =============================================================================
@app.route('/')
def index():
    """Servir la página principal (requiere login)"""
    if 'user' not in session:
        return redirect('/login')
    try:
        tablero_html = frontend_dir / 'tablero.html'
        with open(tablero_html, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return f"tablero.html not found at {tablero_html}", 404

@app.route('/teamviewer.js')
def serve_teamviewer_js():
    """Servir el JavaScript de integración con TeamViewer"""
    js_content = f"""
async function connectTeamViewer(ip) {{
    try {{
        const teamviewerUrl = `teamviewer10://control?device=${{ip}}&password={TEAMVIEWER_PASSWORD}&instant=1`;
        window.location.href = teamviewerUrl;
        console.log(`✅ Conectando a TeamViewer: ${{ip}} con contraseña automática`);
        
        fetch('/api/teamviewer/connect', {{
            method: 'POST',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{ ip: ip }})
        }}).catch(err => console.log('Error logging:', err));
    }} catch (error) {{
        console.error('Error conectando TeamViewer:', error);
        alert(`⚠️ Error al conectar TeamViewer a ${{ip}}`);
    }}
}}
console.log('✅ TeamViewer Integration loaded with auto-password');
"""
    return js_content, 200, {'Content-Type': 'application/javascript; charset=utf-8'}

@app.route('/favicon.ico')
def favicon():
    """Servir favicon del sitio"""
    try:
        # Primero buscar en assets
        if (assets_dir / 'favicon.ico').exists():
            return send_from_directory(str(assets_dir), 'favicon.ico', mimetype='image/vnd.microsoft.icon')
        # Fallback a la raíz de frontend
        if (frontend_dir / 'favicon.ico').exists():
            return send_from_directory(str(frontend_dir), 'favicon.ico', mimetype='image/vnd.microsoft.icon')
    except Exception:
        pass
    return '', 404

@app.route('/assets/<path:filename>')
def serve_assets(filename):
    """Servir archivos estáticos desde frontend/assets/"""
    try:
        return send_from_directory(str(assets_dir), filename)
    except Exception as e:
        logging.error(f"Error sirviendo asset {filename}: {str(e)}")
        return '', 404

@app.route('/<path:filename>')
def serve_static_files(filename):
    """Servir otros archivos estáticos"""
    try:
        # Si es una imagen/archivo común, buscar en frontend
        allowed_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.svg', '.css', '.js', '.ico','.eot','.woff2','.woff','.ttf'}
        file_ext = os.path.splitext(filename)[1].lower()
        
        if file_ext in allowed_extensions:
            # Buscar en el directorio frontend calculado dinámicamente
            if (frontend_dir / filename).exists():
                return send_from_directory(str(frontend_dir), filename)
        
        return '', 404
    except Exception as e:
        logging.error(f"Error sirviendo archivo {filename}: {str(e)}")
        return '', 404


# =============================================================================
# ENDPOINTS API - DATOS (PROTEGIDOS)
# =============================================================================
@app.route('/api/active_users', methods=['GET'])
@login_required
def get_active_users():
    """Endpoint: Obtener usuarios activos (actualiza desde Oracle)"""
    try:
        update_active_users_from_db()
        
        clean_cache = {}
        for key, value in active_users_cache.items():
            clean_cache[str(key)] = {
                'usuario': convert_java_to_python(value.get('usuario')),
                'nombre': convert_java_to_python(value.get('nombre', '')),
                'station': convert_java_to_python(value.get('station')),
                'hora': convert_java_to_python(value.get('hora')),
                'wasRetMapped': value.get('wasRetMapped', False),  # ✅ NUEVO
                'originalStation': value.get('originalStation', '')  # ✅ NUEVO
            }
        
        return jsonify({
            'success': True,
            'active_users': clean_cache,
            'total_active': len(clean_cache),
            'timestamp': datetime.now().isoformat(),
            'cache_age_seconds': 0,
            'from_database': True
        })
    except Exception as e:
        logging.error(f"❌ Error en endpoint active_users: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/machines', methods=['GET'])
@login_required
def get_machines():
    """Endpoint: Obtener lista completa de máquinas"""
    organized_machines = {}
    for dept, puestos in machines_config.items():
        organized_machines[dept] = []
        for puesto, ip in sorted(puestos.items()):
            key = f"{dept}-{puesto}"
            user_info = active_users_cache.get(key, {})
            has_rfid = dept in rfid_config and puesto in rfid_config[dept]
            rfid_ip = rfid_config.get(dept, {}).get(puesto, None)
            
            if dept == 'packing':
                puesto_nombre = f"PACK-{puesto}"
            elif dept == 'return':
                puesto_nombre = f"RET-{puesto}"
            elif dept == 'vas':
                puesto_nombre = f"VAS-{puesto}"
            else:
                puesto_nombre = str(puesto)
            
            organized_machines[dept].append({
                'puesto': str(puesto_nombre),
                'ip': str(ip),
                'department': str(dept),
                'user_active': bool(len(user_info) > 0),
                'user_name': convert_java_to_python(user_info.get('usuario', None)),
                'has_rfid': bool(has_rfid),
                'rfid_ip': str(rfid_ip) if rfid_ip else None
            })
    
    total_rfid = sum(len(puestos) for puestos in rfid_config.values())
    return jsonify({
        'success': True,
        'machines': organized_machines,
        'timestamp': datetime.now().isoformat(),
        'total_machines': sum(len(puestos) for puestos in machines_config.values()),
        'total_active_users': len(active_users_cache),
        'total_rfid_devices': total_rfid
    })

@app.route('/api/bulk_ping', methods=['POST'])
@login_required
def bulk_ping_endpoint():
    """Endpoint: Hacer ping a múltiples IPs"""
    try:
        data = request.get_json()
        if not data or 'ips' not in data:
            return jsonify({
                'success': False,
                'error': 'IPs list is required'
            }), 400
        
        ips = data['ips']
        timeout = data.get('timeout', 3)
        results = {}
        
        # ✅ Retardo simulado solicitado por el usuario (ajustado para no ser excesivo)
        # Solo lo aplicamos si hay suficientes IPs (lo que indica el dashboard completo)
        if len(ips) > 10:
            import time
            time.sleep(1.5) # Reducido un poco para compensar otros delays
        
        def ping_worker(ip):
            try:
                success, ping_time, error = ping_ip(ip, timeout)
                results[ip] = {
                    'success': success,
                    'ping_time': ping_time if success else 0,
                    'ip': ip,
                    'timestamp': datetime.now().isoformat()
                }
                if error and not success:
                    results[ip]['error'] = error
            except Exception as e:
                results[ip] = {
                    'success': False,
                    'ping_time': 0,
                    'ip': ip,
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                }
        
        import time
        start_time = time.time()
        
        futures = [executor.submit(ping_worker, ip) for ip in ips]
        # Reducimos el timeout del join para no bloquear demasiado
        for future in futures:
            try:
                future.result(timeout=timeout + 1)
            except Exception as e:
                pass # Errores individuales ya se loguean en ping_worker
        
        end_time = time.time()
        total_time = round((end_time - start_time) * 1000, 2)
        successful_pings = sum(1 for result in results.values() if result['success'])
        
        return jsonify({
            'success': True,
            'results': results,
            'total': len(ips),
            'successful': successful_pings,
            'failed': len(ips) - successful_pings,
            'duration_ms': total_time,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logging.error(f"❌ Error in bulk ping: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# =============================================================================
# ENDPOINTS API - INCIDENCIAS (mantener existentes)
# =============================================================================
@app.route('/api/tipos_incidencias', methods=['GET'])
@login_required
def get_tipos_incidencias():
    """Obtener tipos de incidencias"""
    return jsonify({
        'success': True,
        'tipos': tipos_incidencias
    })

@app.route('/api/incidencias', methods=['POST'])
@login_required
@limiter.limit("30 per minute")  # Rate limiting: máximo 30 incidencias por minuto
def crear_incidencia():
    """Crear nueva incidencia en MySQL"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'Datos de entrada inválidos'
            }), 400
        
        user = session['user']
        
        # ✅ VALIDAR DATOS DE ENTRADA
        is_valid, error_msg, validated_data = validate_incidencia_data(data)
        if not is_valid:
            return jsonify({
                'success': False,
                'error': error_msg
            }), 400
        
        # ✅ PROTECCIÓN CONTRA DUPLICADOS: Verificar si ya existe una incidencia similar reciente
        departamento = validated_data['departamento']
        puesto = validated_data['puesto']
        categoria = validated_data['categoria']
        
        # Verificar duplicados en los últimos 60 segundos
        incidencias_existentes = mysql_db.get_todas_incidencias()
        from datetime import datetime, timedelta
        ahora = datetime.now()
        limite_tiempo = ahora - timedelta(seconds=60)
        
        for inc in incidencias_existentes:
            # Convertir puesto a string para evitar error 'int' object has no attribute 'upper'
            inc_puesto = str(inc.get('puesto', ''))
            puesto_str = str(puesto)
            if (inc.get('departamento', '').lower() == departamento and 
                inc_puesto.upper() == puesto_str.upper() and 
                inc.get('categoria', '').upper() == categoria.upper() and
                inc.get('estado') in ['pendiente', 'en_proceso']):
                
                # Verificar si fue creada hace poco
                fecha_creacion = inc.get('fecha_creacion')
                if fecha_creacion:
                    if isinstance(fecha_creacion, str):
                        fecha_creacion = datetime.fromisoformat(fecha_creacion.replace('Z', '+00:00'))
                    
                    if fecha_creacion.replace(tzinfo=None) > limite_tiempo:
                        logging.warning(f"⚠️ Incidencia duplicada bloqueada: {departamento}-{puesto}-{categoria}")
                        return jsonify({
                            'success': False,
                            'error': f'Ya existe una incidencia similar activa para este puesto (ID: {inc.get("id")}). Espera antes de reportar la misma incidencia.'
                        }), 409  # Conflict
        
        # ✅ CREAR INCIDENCIA: usar datos validados
        nueva_incidencia = mysql_db.crear_incidencia(
            datos=validated_data,
            reportado_por_nombre=user['nombre_completo'],
            reportado_por_username=user['username']
        )
        
        if nueva_incidencia:
            logging.info(f"✅ Incidencia creada: {nueva_incidencia['id']} por {user['username']}")
            
            # ✨ AUTO-REINICIO RFID SI ES INCIDENCIA DE "RFID NO LEE" O "ITEM NOT FOUND"
            categoria = data.get('categoria', '').upper()
            if categoria in ['RFID_NO_LEE', 'RFID NO LEE', 'ITEM_NOT_FOUND']:
                try:
                    # Obtener la IP del RFID del puesto
                    department = data.get('departamento', '').lower()
                    puesto_raw = data.get('puesto', '')
                    
                    # Extraer número de puesto
                    if isinstance(puesto_raw, str) and '-' in puesto_raw:
                        puesto_num = int(puesto_raw.split('-')[1])
                    else:
                        puesto_num = int(puesto_raw)
                    
                    # Buscar RFID IP en la configuración
                    rfid_ip = rfid_config.get(department, {}).get(puesto_num)
                    
                    if rfid_ip:
                        logging.info(f"🔄 Auto-reinicio RFID detectado para {department.upper()}-{puesto_num} (IP: {rfid_ip})")
                        success, mensaje = ejecutar_ssh_reboot(rfid_ip, RFID_SSH_PASSWORD)
                        
                        if success:
                            # Registrar evento de auto-reinicio en el historial
                            mysql_db.registrar_evento_historial(
                                incidencia_id=nueva_incidencia['id'],
                                tipo_evento='AUTO_RFID_REBOOT',
                                descripcion=f"✅ Reinicio automático del RFID enviado por el sistema a {rfid_ip}",
                                usuario='Sistema',
                                username='auto_system'
                            )
                            logging.info(f"✅ Auto-reinicio RFID exitoso: {department.upper()}-{puesto_num}")
                        else:
                            logging.warning(f"⚠️ Auto-reinicio RFID falló: {mensaje}")
                    else:
                        logging.warning(f"⚠️ No se encontró RFID configurado para {department.upper()}-{puesto_num}")
                        
                except Exception as e_rfid:
                    logging.error(f"❌ Error en auto-reinicio RFID: {str(e_rfid)}")
                    # No fallamos toda la creación si el auto-reinicio falla
            
            return jsonify({
                'success': True,
                'incidencia': nueva_incidencia
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Error al crear incidencia en MySQL'
            }), 500
            
    except Exception as e:
        logging.error(f"❌ Error creando incidencia: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
    
@app.route('/api/incidencias', methods=['GET'])
@login_required
def get_incidencias():
    """Obtener todas las incidencias"""
    try:
        if mysql_db is None:
            return jsonify({
                'success': False,
                'error': 'Sistema de incidencias no disponible'
            }), 503
        
        incidencias = mysql_db.get_todas_incidencias()
        
        return jsonify({
            'success': True,
            'incidencias': incidencias
        })
    except Exception as e:
        logging.error(f"❌ Error obteniendo incidencias: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/incidencias/<int:inc_id>', methods=['PUT'])
@login_required
def actualizar_incidencia(inc_id):
    """Actualizar incidencia en MySQL"""
    try:
        data = request.get_json()
        user = session['user']
        
        nuevo_estado = data.get('estado')
        notas = data.get('notas_resolucion', '')
        
        incidencia_actualizada = mysql_db.actualizar_estado_incidencia(
            incidencia_id=inc_id,
            nuevo_estado=nuevo_estado,
            resuelto_por=user['nombre_completo'],
            notas=notas,
            resuelto_por_username=user['username']
        )
        
        if incidencia_actualizada:
            logging.info(f"✅ Incidencia actualizada: {inc_id} por {user['username']}")
            return jsonify({
                'success': True,
                'incidencia': incidencia_actualizada
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Incidencia no encontrada'
            }), 404
            
    except Exception as e:
        logging.error(f"❌ Error actualizando incidencia: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# =============================================================================
# ENDPOINTS API - SISTEMA DE PAUSAS
# =============================================================================

@app.route('/api/motivos-pausa', methods=['GET'])
@login_required
def get_motivos_pausa():
    """Obtener lista de motivos de pausa disponibles"""
    try:
        if not mysql_db:
            return jsonify({'success': False, 'error': 'Sistema no disponible'}), 503
        
        motivos = mysql_db.get_motivos_pausa(activos_solo=True)
        return jsonify({
            'success': True,
            'motivos': motivos
        })
    except Exception as e:
        logging.error(f"❌ Error obteniendo motivos de pausa: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/motivos-pausa', methods=['POST'])
@login_required
def crear_motivo_pausa():
    """Crear nuevo motivo de pausa (solo IT_ADMIN)"""
    try:
        user = session['user']
        if user['rol'] != 'IT_ADMIN':
            return jsonify({'success': False, 'error': 'No autorizado'}), 403
        
        data = request.get_json()
        codigo = data.get('codigo', '').strip().upper()
        descripcion = data.get('descripcion', '').strip()
        requiere_descripcion = data.get('requiere_descripcion', False)
        orden = data.get('orden', 50)
        
        if not codigo or not descripcion:
            return jsonify({'success': False, 'error': 'Código y descripción requeridos'}), 400
        
        if mysql_db.crear_motivo_pausa(codigo, descripcion, requiere_descripcion, orden):
            return jsonify({
                'success': True,
                'message': f'Motivo {codigo} creado correctamente'
            })
        else:
            return jsonify({'success': False, 'error': 'Error al crear motivo'}), 500
            
    except Exception as e:
        logging.error(f"❌ Error creando motivo de pausa: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/motivos-pausa/<codigo>', methods=['PUT'])
@login_required
def actualizar_motivo_pausa(codigo):
    """Actualizar motivo de pausa (solo IT_ADMIN)"""
    try:
        user = session['user']
        if user['rol'] != 'IT_ADMIN':
            return jsonify({'success': False, 'error': 'No autorizado'}), 403
        
        data = request.get_json()
        
        if mysql_db.actualizar_motivo_pausa(
            codigo,
            descripcion=data.get('descripcion'),
            activo=data.get('activo'),
            orden=data.get('orden')
        ):
            return jsonify({'success': True, 'message': 'Motivo actualizado'})
        else:
            return jsonify({'success': False, 'error': 'Motivo no encontrado'}), 404
            
    except Exception as e:
        logging.error(f"❌ Error actualizando motivo: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/incidencias/<int:inc_id>/pausar', methods=['POST'])
@login_required
def pausar_incidencia(inc_id):
    """Pausar una incidencia (solo IT_ADMIN)"""
    try:
        user = session['user']
        if user['rol'] != 'IT_ADMIN':
            return jsonify({'success': False, 'error': 'No autorizado'}), 403
        
        data = request.get_json() or {}
        motivo_codigo = (data.get('motivo') or '').strip()
        descripcion_adicional = (data.get('descripcion') or '').strip() or None
        
        if not motivo_codigo:
            return jsonify({'success': False, 'error': 'Motivo requerido'}), 400
        
        incidencia = mysql_db.pausar_incidencia(
            incidencia_id=inc_id,
            motivo_codigo=motivo_codigo,
            usuario=user['nombre_completo'],
            username=user['username'],
            descripcion_adicional=descripcion_adicional
        )
        
        if incidencia:
            logging.info(f"⏸️ Incidencia {inc_id} pausada por {user['username']}")
            return jsonify({
                'success': True,
                'incidencia': incidencia,
                'message': 'Incidencia pausada correctamente'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'No se pudo pausar la incidencia'
            }), 400
            
    except Exception as e:
        logging.error(f"❌ Error pausando incidencia: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/incidencias/<int:inc_id>/reanudar', methods=['POST'])
@login_required
def reanudar_incidencia(inc_id):
    """Reanudar una incidencia pausada (solo IT_ADMIN)"""
    try:
        user = session['user']
        if user['rol'] != 'IT_ADMIN':
            return jsonify({'success': False, 'error': 'No autorizado'}), 403
        
        data = request.get_json() or {}
        notas = data.get('notas', '').strip() or None
        
        incidencia = mysql_db.reanudar_incidencia(
            incidencia_id=inc_id,
            usuario=user['nombre_completo'],
            username=user['username'],
            notas=notas
        )
        
        if incidencia:
            logging.info(f"▶️ Incidencia {inc_id} reanudada por {user['username']}")
            return jsonify({
                'success': True,
                'incidencia': incidencia,
                'message': 'Incidencia reanudada correctamente'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'No se pudo reanudar la incidencia'
            }), 400
            
    except Exception as e:
        logging.error(f"❌ Error reanudando incidencia: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/incidencias/<int:inc_id>/timeline', methods=['GET'])
@login_required
def get_timeline_incidencia(inc_id):
    """Obtener línea temporal de una incidencia"""
    try:
        if user_session := session.get('user'):
            if user_session['rol'] != 'IT_ADMIN':
                return jsonify({'success': False, 'error': 'No autorizado'}), 403
        
        timeline = mysql_db.get_timeline_incidencia(inc_id)
        pausas = mysql_db.get_historial_pausas(inc_id)
        
        return jsonify({
            'success': True,
            'timeline': timeline,
            'pausas': pausas,
            'total_eventos': len(timeline),
            'total_pausas': len(pausas)
        })
        
    except Exception as e:
        logging.error(f"❌ Error obteniendo timeline: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/incidencias/<int:inc_id>/pausas', methods=['GET'])
@login_required
def get_pausas_incidencia(inc_id):
    """Obtener historial de pausas de una incidencia"""
    try:
        pausas = mysql_db.get_historial_pausas(inc_id)
        
        # Calcular totales
        total_minutos = sum(p.get('duracion_minutos', 0) or 0 for p in pausas if not p.get('activa'))
        
        return jsonify({
            'success': True,
            'pausas': pausas,
            'total_pausas': len(pausas),
            'total_minutos_pausado': total_minutos,
            'pausa_activa': any(p.get('activa') for p in pausas)
        })
        
    except Exception as e:
        logging.error(f"❌ Error obteniendo pausas: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/estadisticas/pausas', methods=['GET'])
@login_required
def get_estadisticas_pausas():
    """Obtener estadísticas de pausas (solo IT_ADMIN)"""
    try:
        user = session['user']
        if user['rol'] != 'IT_ADMIN':
            return jsonify({'success': False, 'error': 'No autorizado'}), 403
        
        stats = mysql_db.get_estadisticas_pausas()
        
        return jsonify({
            'success': True,
            'estadisticas': stats
        })
        
    except Exception as e:
        logging.error(f"❌ Error obteniendo estadísticas de pausas: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

# =============================================================================
# ENDPOINTS API - ANALYTICS AVANZADO
# =============================================================================

@app.route('/api/analytics/estadisticas', methods=['GET'])
@login_required
def get_estadisticas_avanzadas():
    """Obtener estadísticas avanzadas con filtros"""
    try:
        fecha_inicio = request.args.get('fecha_inicio')
        fecha_fin = request.args.get('fecha_fin')
        departamento = request.args.get('departamento')
        
        stats = mysql_db.get_estadisticas_avanzadas(
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            departamento=departamento
        )
        
        return jsonify({
            'success': True,
            'estadisticas': stats
        })
        
    except Exception as e:
        logging.error(f"❌ Error obteniendo estadísticas avanzadas: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/analytics/sla', methods=['GET'])
@login_required
def get_sla_compliance():
    """Obtener cumplimiento de SLA"""
    try:
        sla_horas = request.args.get('sla_horas', 4, type=int)
        fecha_inicio = request.args.get('fecha_inicio')
        fecha_fin = request.args.get('fecha_fin')
        
        sla = mysql_db.get_sla_compliance(
            sla_horas=sla_horas,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin
        )
        
        return jsonify({
            'success': True,
            'sla': sla
        })
        
    except Exception as e:
        logging.error(f"❌ Error obteniendo SLA: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/analytics/tiempos-pausas', methods=['GET'])
@login_required
def get_tiempos_por_motivo():
    """Obtener tiempos por motivo de pausa"""
    try:
        fecha_inicio = request.args.get('fecha_inicio')
        fecha_fin = request.args.get('fecha_fin')
        
        tiempos = mysql_db.get_tiempos_por_motivo_pausa(
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin
        )
        
        return jsonify({
            'success': True,
            'tiempos': tiempos
        })
        
    except Exception as e:
        logging.error(f"❌ Error obteniendo tiempos por motivo: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/analytics/tiempos-efectivo', methods=['GET'])
@login_required
def get_tiempos_efectivo():
    """Obtener comparación tiempo efectivo vs total"""
    try:
        # ✅ ACEPTAR TANTO FILTROS DE FECHA COMO DÍAS
        fecha_inicio = request.args.get('fecha_inicio')
        fecha_fin = request.args.get('fecha_fin')
        dias = request.args.get('dias', 30, type=int)
        
        tiempos = mysql_db.get_tiempos_efectivo_vs_total(
            dias=dias,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin
        )
        
        return jsonify({
            'success': True,
            'tiempos': tiempos
        })
        
    except Exception as e:
        logging.error(f"❌ Error obteniendo tiempos efectivo: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/analytics/eficiencia-tecnicos', methods=['GET'])
@login_required
def get_eficiencia_tecnicos():
    """Obtener eficiencia por técnico"""
    try:
        fecha_inicio = request.args.get('fecha_inicio')
        fecha_fin = request.args.get('fecha_fin')
        
        eficiencia = mysql_db.get_eficiencia_tecnicos(
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin
        )
        
        return jsonify({
            'success': True,
            'tecnicos': eficiencia
        })
        
    except Exception as e:
        logging.error(f"❌ Error obteniendo eficiencia: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/analytics/exportar', methods=['GET'])
@login_required
def exportar_incidencias():
    """Exportar incidencias en formato JSON para CSV"""
    try:
        user = session['user']
        if user['rol'] != 'IT_ADMIN':
            return jsonify({'success': False, 'error': 'No autorizado'}), 403
        
        fecha_inicio = request.args.get('fecha_inicio')
        fecha_fin = request.args.get('fecha_fin')
        departamento = request.args.get('departamento')
        
        datos = mysql_db.exportar_incidencias_csv(
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            departamento=departamento
        )
        
        return jsonify({
            'success': True,
            'datos': datos,
            'total': len(datos)
        })
        
    except Exception as e:
        logging.error(f"❌ Error exportando incidencias: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/analytics/powerbi', methods=['GET'])
@login_required
def get_analytics_powerbi():
    """
    Exportar datos de analytics en formato optimizado para Power BI Desktop.
    Formato JSON plano que Power BI puede importar directamente.
    """
    try:
        user = session['user']
        if user['rol'] != 'IT_ADMIN':
            return jsonify({'success': False, 'error': 'No autorizado'}), 403
        
        fecha_inicio = request.args.get('fecha_inicio')
        fecha_fin = request.args.get('fecha_fin')
        departamento = request.args.get('departamento', 'todos')
        
        if not mysql_db:
            return jsonify({'success': False, 'error': 'Sistema no disponible'}), 503
        
        # Obtener todas las incidencias con datos completos
        incidencias_raw = mysql_db.exportar_incidencias_csv(
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            departamento=departamento if departamento != 'todos' else None
        )
        
        # Transformar a formato plano para Power BI
        datos_powerbi = []
        for inc in incidencias_raw:
            datos_powerbi.append({
                'ID': inc.get('id'),
                'Departamento': inc.get('departamento', '').upper(),
                'Puesto': str(inc.get('puesto', '')),
                'Categoria': inc.get('categoria', ''),
                'Descripcion': inc.get('descripcion', ''),
                'Prioridad': inc.get('prioridad', '').upper(),
                'Estado': inc.get('estado', '').upper(),
                'ReportadoPor': inc.get('reportado_por', ''),
                'ResueltoPor': inc.get('resuelto_por', ''),
                'FechaCreacion': inc.get('fecha_creacion', ''),
                'FechaResolucion': inc.get('fecha_resolucion', ''),
                'MinutosTotal': inc.get('minutos_total', 0) or 0,
                'MinutosPausado': inc.get('minutos_pausado', 0) or 0,
                'MinutosEfectivo': inc.get('minutos_efectivo', 0) or 0,
                'HorasTotal': round((inc.get('minutos_total', 0) or 0) / 60, 2),
                'HorasEfectivo': round((inc.get('minutos_efectivo', 0) or 0) / 60, 2),
                'HorasPausado': round((inc.get('minutos_pausado', 0) or 0) / 60, 2),
                'DiasResolucion': round((inc.get('minutos_total', 0) or 0) / (60 * 24), 2) if inc.get('fecha_resolucion') else None,
                'NotasResolucion': inc.get('notas_resolucion', ''),
                'Resuelta': 1 if inc.get('estado') == 'resuelta' else 0,
                'EnProceso': 1 if inc.get('estado') == 'en_proceso' else 0,
                'Pendiente': 1 if inc.get('estado') == 'pendiente' else 0,
                'Pausada': 1 if (inc.get('minutos_pausado', 0) or 0) > 0 else 0
            })
        
        return jsonify({
            'success': True,
            'data': datos_powerbi,
            'total': len(datos_powerbi),
            'metadata': {
                'fecha_inicio': fecha_inicio,
                'fecha_fin': fecha_fin,
                'departamento': departamento,
                'exportado_en': datetime.now().isoformat(),
                'formato': 'powerbi_json'
            }
        })
        
    except Exception as e:
        logging.error(f"❌ Error exportando para Power BI: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/analytics/powerbi/csv', methods=['GET'])
@login_required
def get_analytics_powerbi_csv():
    """
    Exportar datos en formato CSV para importar en Power BI Desktop.
    """
    try:
        user = session['user']
        if user['rol'] != 'IT_ADMIN':
            return jsonify({'success': False, 'error': 'No autorizado'}), 403
        
        fecha_inicio = request.args.get('fecha_inicio')
        fecha_fin = request.args.get('fecha_fin')
        departamento = request.args.get('departamento', 'todos')
        
        if not mysql_db:
            return jsonify({'success': False, 'error': 'Sistema no disponible'}), 503
        
        # Obtener datos
        incidencias_raw = mysql_db.exportar_incidencias_csv(
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            departamento=departamento if departamento != 'todos' else None
        )
        
        # Crear CSV
        import csv
        import io
        
        output = io.StringIO()
        fieldnames = [
            'ID', 'Departamento', 'Puesto', 'Categoria', 'Descripcion',
            'Prioridad', 'Estado', 'ReportadoPor', 'ResueltoPor',
            'FechaCreacion', 'FechaResolucion',
            'MinutosTotal', 'MinutosPausado', 'MinutosEfectivo',
            'HorasTotal', 'HorasEfectivo', 'HorasPausado', 'DiasResolucion',
            'NotasResolucion', 'Resuelta', 'EnProceso', 'Pendiente', 'Pausada'
        ]
        
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        
        for inc in incidencias_raw:
            minutos_total = inc.get('minutos_total', 0) or 0
            minutos_efectivo = inc.get('minutos_efectivo', 0) or 0
            minutos_pausado = inc.get('minutos_pausado', 0) or 0
            
            writer.writerow({
                'ID': inc.get('id'),
                'Departamento': inc.get('departamento', '').upper(),
                'Puesto': str(inc.get('puesto', '')),
                'Categoria': inc.get('categoria', ''),
                'Descripcion': inc.get('descripcion', ''),
                'Prioridad': inc.get('prioridad', '').upper(),
                'Estado': inc.get('estado', '').upper(),
                'ReportadoPor': inc.get('reportado_por', ''),
                'ResueltoPor': inc.get('resuelto_por', ''),
                'FechaCreacion': inc.get('fecha_creacion', ''),
                'FechaResolucion': inc.get('fecha_resolucion', ''),
                'MinutosTotal': minutos_total,
                'MinutosPausado': minutos_pausado,
                'MinutosEfectivo': minutos_efectivo,
                'HorasTotal': round(minutos_total / 60, 2),
                'HorasEfectivo': round(minutos_efectivo / 60, 2),
                'HorasPausado': round(minutos_pausado / 60, 2),
                'DiasResolucion': round(minutos_total / (60 * 24), 2) if inc.get('fecha_resolucion') else '',
                'NotasResolucion': inc.get('notas_resolucion', ''),
                'Resuelta': 1 if inc.get('estado') == 'resuelta' else 0,
                'EnProceso': 1 if inc.get('estado') == 'en_proceso' else 0,
                'Pendiente': 1 if inc.get('estado') == 'pendiente' else 0,
                'Pausada': 1 if minutos_pausado > 0 else 0
            })
        
        csv_data = output.getvalue()
        output.close()
        
        return Response(
            csv_data,
            mimetype='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename=analytics_powerbi_{datetime.now().strftime("%Y%m%d")}.csv'
            }
        )
        
    except Exception as e:
        logging.error(f"❌ Error exportando CSV para Power BI: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/analytics/dashboard', methods=['GET'])
@login_required
def get_analytics_dashboard():
    """
    Endpoint consolidado para el dashboard de analytics.
    Devuelve todos los datos necesarios para renderizar los gráficos detallados.
    """
    try:
        # Obtener filtros
        fecha_inicio = request.args.get('fecha_inicio')
        fecha_fin = request.args.get('fecha_fin')
        departamento = request.args.get('departamento', 'todos')
        
        if not mysql_db:
            return jsonify({'success': False, 'error': 'BD no disponible'}), 503
        
        # Obtener todas las incidencias con los filtros
        incidencias = mysql_db.exportar_incidencias_csv(
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            departamento=departamento if departamento != 'todos' else None
        )
        
        logging.info(f"📊 Dashboard Analytics: {len(incidencias)} incidencias encontradas para el rango {fecha_inicio} a {fecha_fin}")
        
        # Calcular métricas generales
        total_incidencias = len(incidencias)
        resueltas = sum(1 for i in incidencias if i.get('estado') == 'resuelta')
        en_proceso = sum(1 for i in incidencias if i.get('estado') == 'en_proceso')
        pendientes = sum(1 for i in incidencias if i.get('estado') == 'pendiente')
        pausadas = sum(1 for i in incidencias if i.get('estado') == 'pausada')
        
        # Tiempo promedio de resolución
        tiempos_resueltas = [i.get('minutos_total', 0) for i in incidencias if i.get('estado') == 'resuelta' and i.get('minutos_total')]
        tiempo_promedio_mins = sum(tiempos_resueltas) / len(tiempos_resueltas) if tiempos_resueltas else 0
        tiempo_promedio_horas = tiempo_promedio_mins / 60.0
        
        # TIMELINE - Incidencias por período (últimos 30 días)
        from datetime import datetime, timedelta
        timeline_data = {}
        for inc in incidencias:
            fecha_str = inc.get('fecha_creacion', '')[:10]  # Solo la fecha (YYYY-MM-DD)
            if fecha_str:
                timeline_data[fecha_str] = timeline_data.get(fecha_str, 0) + 1
        
        timeline_labels = sorted(timeline_data.keys())[-30:]  # Últimos 30 días
        timeline_values = [timeline_data[fecha] for fecha in timeline_labels]
        
        # CATEGORÍAS - Distribución por tipo
        categorias_data = {}
        for inc in incidencias:
            cat = inc.get('categoria', 'Sin categoría')
            categorias_data[cat] = categorias_data.get(cat, 0) + 1
        
        categorias_labels = list(categorias_data.keys())
        categorias_values = list(categorias_data.values())
        
        # DEPARTAMENTOS - Distribución por departamento
        dept_data = {}
        for inc in incidencias:
            dept = inc.get('departamento', 'Sin dept').upper()
            dept_data[dept] = dept_data.get(dept, 0) + 1
        
        dept_labels = list(dept_data.keys())
        dept_values = list(dept_data.values())
        
        # TIEMPOS PROMEDIO - Por categoría
        tiempo_por_cat = {}
        count_por_cat = {}
        for inc in incidencias:
            cat = inc.get('categoria', 'Sin categoría')
            mins = inc.get('minutos_total', 0) or 0
            if mins > 0:
                tiempo_por_cat[cat] = tiempo_por_cat.get(cat, 0) + mins
                count_por_cat[cat] = count_por_cat.get(cat, 0) + 1
        
        tiempo_labels = []
        tiempo_values = []
        for cat, total_mins in tiempo_por_cat.items():
            count = count_por_cat[cat]
            promedio = total_mins / count if count > 0 else 0
            tiempo_labels.append(cat)
            tiempo_values.append(round(promedio, 1))
        
        # TOP REPORTAN - Usuarios que más reportan
        reportan_data = {}
        for inc in incidencias:
            usuario = inc.get('reportado_por', 'Desconocido')
            reportan_data[usuario] = reportan_data.get(usuario, 0) + 1
        
        top_reportan = sorted(reportan_data.items(), key=lambda x: x[1], reverse=True)[:5]
        reportan_labels = [u[0] for u in top_reportan]
        reportan_values = [u[1] for u in top_reportan]
        
        # TOP RESUELVEN - Técnicos que más resuelven
        resuelven_data = {}
        for inc in incidencias:
            if inc.get('estado') == 'resuelta':
                tecnico = inc.get('resuelto_por', 'Sin asignar')
                if tecnico:
                    resuelven_data[tecnico] = resuelven_data.get(tecnico, 0) + 1
        
        top_resuelven = sorted(resuelven_data.items(), key=lambda x: x[1], reverse=True)[:5]
        resuelven_labels = [t[0] for t in top_resuelven]
        resuelven_values = [t[1] for t in top_resuelven]
        
        # HORAS PICO - Distribución por hora del día
        horas_data = {h: 0 for h in range(24)}
        for inc in incidencias:
            fecha_str = inc.get('fecha_creacion', '')
            if len(fecha_str) >= 13:  # YYYY-MM-DD HH:MM
                try:
                    hora = int(fecha_str[11:13])
                    horas_data[hora] = horas_data.get(hora, 0) + 1
                except:
                    pass
        
        horas_labels = [f"{h}:00" for h in range(24)]
        horas_values = [horas_data[h] for h in range(24)]
        
        # PUESTOS PROBLEMÁTICOS - Top 5 puestos con más incidencias
        puestos_data = {}
        for inc in incidencias:
            dept = inc.get('departamento', '').upper()
            puesto = inc.get('puesto', '')
            puesto_completo = f"{dept}-{puesto}"
            puestos_data[puesto_completo] = puestos_data.get(puesto_completo, 0) + 1
        
        top_puestos = sorted(puestos_data.items(), key=lambda x: x[1], reverse=True)[:5]
        puestos_labels = [p[0] for p in top_puestos]
        puestos_values = [p[1] for p in top_puestos]
        
        # Comparativa mensual y tendencia
        hoy = datetime.now()
        mes_ant_date = hoy.replace(day=1) - timedelta(days=1)
        mes_actual_count = 0
        mes_anterior_count = 0
        hace7 = hoy.date() - timedelta(days=7)
        hace14 = hoy.date() - timedelta(days=14)
        sem_actual = 0
        sem_anterior = 0
        
        for inc in incidencias:
            try:
                f_str = inc.get('fecha_creacion', '')[:10]
                if f_str:
                    f = datetime.strptime(f_str, '%Y-%m-%d')
                    f_date = f.date()
                    if f.month == hoy.month and f.year == hoy.year:
                        mes_actual_count += 1
                    elif f.month == mes_ant_date.month and f.year == mes_ant_date.year:
                        mes_anterior_count += 1
                    
                    if f_date >= hace7:
                        sem_actual += 1
                    elif f_date >= hace14:
                        sem_anterior += 1
            except:
                pass
        
        pct_cambio = round(((sem_actual - sem_anterior) / sem_anterior * 100), 1) if sem_anterior > 0 else 0
        
        # Si no hay incidencias, generar datos demo
        if total_incidencias == 0:
            from datetime import timedelta as td
            hoy_demo = datetime.now()
            labels_demo = []
            data_demo = []
            for i in range(29, -1, -1):
                dia = hoy_demo - td(days=i)
                labels_demo.append(dia.strftime('%d/%m'))
                data_demo.append(random.randint(3, 12) if dia.weekday() < 5 else random.randint(0, 3))
            
            total_demo = sum(data_demo)
            res_demo = int(total_demo * 0.72)
            
            stats = {
                'metricasGenerales': {
                    'totalIncidencias': total_demo,
                    'resueltas': res_demo,
                    'enProceso': int(total_demo * 0.15),
                    'pendientes': total_demo - res_demo - int(total_demo * 0.15),
                    'pausadas': int(total_demo * 0.08),
                    'tiempoPromedioResolucionHoras': round(random.uniform(1.5, 4.2), 1),
                    'tiempoEfectivoHoras': round(random.uniform(80, 140), 1),
                    'tiempoPausadoHoras': round(random.uniform(15, 35), 1),
                    'ratioResolucion': round((res_demo / max(total_demo, 1)) * 100, 1)
                },
                'incidenciasPorPeriodo': {'labels': labels_demo, 'data': data_demo},
                'distribucionCategorias': {
                    'labels': ['RFID No Lee', 'Impresora Zebra', 'PC Lento', 'Pantalla', 'Item No Found', 'Otros'],
                    'data': [int(total_demo*0.28), int(total_demo*0.22), int(total_demo*0.18), int(total_demo*0.12), int(total_demo*0.10), int(total_demo*0.10)]
                },
                'departamentos': {'labels': ['Packing', 'Return', 'VAS'], 'data': [int(total_demo*0.60), int(total_demo*0.28), int(total_demo*0.12)]},
                'tiempoResolucion': {'labels': ['RFID No Lee', 'Impresora Zebra', 'PC Lento', 'Pantalla', 'Item No Found', 'Otros'], 'data': [2.1, 1.5, 3.8, 2.5, 0.8, 1.2]},
                'usuariosReportan': {'labels': ['admin', 'supervisor', 'jefe_packing', 'tecnico1'], 'data': [int(total_demo*0.35), int(total_demo*0.25), int(total_demo*0.20), int(total_demo*0.20)]},
                'usuariosResuelven': {'labels': ['admin', 'tecnico1', 'tecnico2', 'supervisor'], 'data': [int(res_demo*0.45), int(res_demo*0.30), int(res_demo*0.15), int(res_demo*0.10)]},
                'horasPico': {'labels': [f'{h:02d}:00' for h in range(6, 22)], 'data': [2, 5, 12, 15, 10, 8, 6, 4, 7, 11, 14, 9, 5, 3, 2, 1]},
                'puestosProblematicos': {'labels': ['PACK-12', 'PACK-34', 'RET-8', 'PACK-7', 'VAS-3'], 'data': [8, 6, 5, 4, 3]},
                'comparativaMensual': {'mesActual': total_demo, 'mesAnterior': int(total_demo * random.uniform(0.8, 1.3)), 'mesActualLabel': hoy_demo.strftime('%B %Y'), 'mesAnteriorLabel': (hoy_demo - td(days=30)).strftime('%B %Y')},
                'tendenciaSemanal': {'semanaActual': sum(data_demo[-7:]), 'semanaAnterior': sum(data_demo[-14:-7])},
                'sla': {'porcentaje': round(random.uniform(78, 95), 1), 'objetivo': '4h', 'dentro': int(res_demo * 0.85), 'fuera': int(res_demo * 0.15)}
            }
            return jsonify({'success': True, 'stats': stats, 'total_incidencias': total_demo})

        # Calcular ratio y tiempos adicionales
        ratio_resolucion = round((resueltas / max(total_incidencias, 1)) * 100, 1)
        tiempo_efectivo = round(sum(i.get('minutos_efectivo', i.get('minutos_total', 0)) or 0 for i in incidencias if i.get('estado') == 'resuelta') / 60.0, 1)
        tiempo_pausado = round(sum(i.get('minutos_pausado', 0) or 0 for i in incidencias) / 60.0, 1)
        
        # SLA
        sla_objetivo_mins = 4 * 60
        dentro_sla = sum(1 for i in incidencias if i.get('estado') == 'resuelta' and (i.get('minutos_total', 0) or 0) <= sla_objetivo_mins)
        fuera_sla = resueltas - dentro_sla
        sla_pct = round((dentro_sla / max(resueltas, 1)) * 100, 1)
        
        # Construir respuesta compatible con el frontend
        stats = {
            'metricasGenerales': {
                'totalIncidencias': total_incidencias,
                'resueltas': resueltas,
                'enProceso': en_proceso,
                'pendientes': pendientes,
                'pausadas': pausadas,
                'tiempoPromedioResolucionHoras': round(tiempo_promedio_horas, 1),
                'tiempoEfectivoHoras': tiempo_efectivo,
                'tiempoPausadoHoras': tiempo_pausado,
                'ratioResolucion': ratio_resolucion
            },
            'incidenciasPorPeriodo': {
                'labels': timeline_labels,
                'data': timeline_values
            },
            'distribucionCategorias': {
                'labels': categorias_labels,
                'data': categorias_values
            },
            'departamentos': {
                'labels': dept_labels,
                'data': dept_values
            },
            'tiempoResolucion': {
                'labels': tiempo_labels,
                'data': tiempo_values
            },
            'usuariosReportan': {
                'labels': reportan_labels,
                'data': reportan_values
            },
            'usuariosResuelven': {
                'labels': resuelven_labels,
                'data': resuelven_values
            },
            'horasPico': {
                'labels': horas_labels,
                'data': horas_values
            },
            'puestosProblematicos': {
                'labels': puestos_labels,
                'data': puestos_values
            },
            'comparativaMensual': {
                'mesActual': mes_actual_count,
                'mesAnterior': mes_anterior_count,
                'mesActualLabel': hoy.strftime('%B %Y').capitalize(),
                'mesAnteriorLabel': mes_ant_date.strftime('%B %Y').capitalize()
            },
            'tendenciaSemanal': {
                'semanaActual': sem_actual,
                'semanaAnterior': sem_anterior
            },
            'sla': {
                'porcentaje': sla_pct,
                'objetivo': '4h',
                'dentro': dentro_sla,
                'fuera': fuera_sla
            }
        }
        
        return jsonify({
            'success': True,
            'stats': stats,
            'total_incidencias': total_incidencias
        })
        
    except Exception as e:
        logging.error(f"❌ Error en analytics dashboard: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


# =============================================================================
# ENDPOINTS API - CONFIGURACIÓN DE IMPRESORAS ZEBRA
# =============================================================================

@app.route('/api/zebra/config', methods=['POST'])
@login_required
def configure_zebra_printer():
    """Configurar impresora Zebra (ZPL) con autenticación"""
    try:
        user = session['user']
        if user['rol'] != 'IT_ADMIN':
            return jsonify({'success': False, 'error': 'No autorizado'}), 403

        data = request.json
        ip = data.get('ip')
        darkness = data.get('darkness')
        left = data.get('left')  # Posición izquierda (Label Shift)
        top = data.get('top')
        speed = data.get('speed')
        password = data.get('password', '1234')  # ✅ Contraseña por defecto 1234

        if not ip:
            return jsonify({'success': False, 'error': 'IP de impresora requerida'}), 400

        logging.info(f"🖨️ Configurando Zebra {ip}: Darkness={darkness}, Left={left}, Top={top}, Speed={speed}")

        # ============================================================
        # USAR MÉTODO SGD (Set-Get-Do) - FUNCIONA con ZD420/ZD421
        # ============================================================
        sgd_cmds = []
        
        # Darkness/Tone (0-30) - print.tone es el parámetro correcto
        if darkness is not None:
            val = max(0, min(30, int(darkness)))
            sgd_cmds.append(f'! U1 setvar "print.tone" "{val}"')
        
        # Left Position (posición izquierda)
        if left is not None:
            val = int(left)
            sgd_cmds.append(f'! U1 setvar "zpl.left_position" "{val}"')
        
        # Top Position (posición superior)  
        if top is not None:
            val = int(top)
            sgd_cmds.append(f'! U1 setvar "zpl.top_position" "{val}"')
        
        # Print Speed (velocidad)
        if speed is not None:
            val = max(2, min(14, int(speed)))
            sgd_cmds.append(f'! U1 setvar "media.speed" "{val}"')
        
        zpl_payload = "\r\n".join(sgd_cmds) + "\r\n"
        logging.info(f"🖨️ Usando método SGD (probado y funcionando)")
        
        
        logging.info(f"🖨️ Enviando ZPL a {ip}:6101")
        logging.info(f"🖨️ Comandos ZPL: {zpl_payload}")
        
        # ✅ Enviar vía Socket directo al puerto Raw (6101)
        # Las impresoras Zebra aceptan comandos ZPL directamente por socket en el puerto raw
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)  # 10 segundos timeout
            
            logging.info(f"📡 Conectando a {ip}:6101...")
            sock.connect((ip, 6101))  # Puerto Raw configurado en la impresora
            
            logging.info(f"📤 Enviando {len(zpl_payload)} bytes de comandos ZPL...")
            sock.sendall(zpl_payload.encode('utf-8'))
            
            # Pequeña pausa para asegurar envío completo
            import time
            time.sleep(0.5)
            
            logging.info(f"✅ Configuración enviada correctamente a {ip}")
            return jsonify({
                'success': True, 
                'message': f'Configuración enviada correctamente a {ip}',
                'zpl_enviado': zpl_payload
            })
            
        except socket.timeout:
            logging.error(f"❌ Timeout conectando a {ip}:6101")
            return jsonify({'success': False, 'error': 'Timeout conectando a impresora. Verifica que la impresora esté encendida y accesible.'}), 504
        except ConnectionRefusedError:
            logging.error(f"❌ Conexión rechazada por {ip}:6101")
            return jsonify({'success': False, 'error': 'Conexión rechazada por impresora. Verifica que el puerto 6101 esté configurado.'}), 502
        except Exception as conn_err:
            logging.error(f"❌ Error de conexión a {ip}: {str(conn_err)}")
            return jsonify({'success': False, 'error': f'Error de conexión: {str(conn_err)}'}), 500
        finally:
            if sock:
                try:
                    sock.close()
                except:
                    pass
        
    except Exception as e:
        logging.error(f"❌ Error interno configurando Zebra: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/zebra/ip', methods=['GET'])
@login_required
def get_zebra_ip_endpoint():
    """Obtener IP de impresora Zebra para un puesto"""
    try:
        dept = request.args.get('departamento')
        puesto = request.args.get('puesto', type=int)
        
        if not dept or not puesto:
            return jsonify({'success': False, 'error': 'Faltan parámetros'}), 400
            
        # Si estamos en modo demo, usar la configuración en memoria
        if IS_DEMO_MODE:
            if dept in zebra_config and puesto in zebra_config[dept]:
                config = zebra_config[dept][puesto]
                return jsonify({
                    'success': True,
                    'zebra': {
                        'ip': config['ip'],
                        'departamento': dept,
                        'puesto': puesto,
                        'darkness_default': 5,
                        'speed_default': 4,
                        'top_default': 0,
                        'tear_off_default': 0
                    }
                })
        
        # Modo real (MySQL)
        zebra = mysql_db.get_zebra_por_puesto(dept, puesto)
        if zebra:
            return jsonify({'success': True, 'zebra': zebra})
        else:
            return jsonify({'success': False, 'error': 'No encontrada'}), 404
            
    except Exception as e:
        logging.error(f"❌ Error buscando IP Zebra: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/zebra/test', methods=['POST'])
@login_required
def test_zebra_unified():
    """Endpoint unificado para probar una o varias impresoras Zebra"""
    try:
        user = session['user']
        if user['rol'] != 'IT_ADMIN':
            return jsonify({'success': False, 'error': 'No autorizado'}), 403

        data = request.get_json()
        ip = data.get('ip')
        impresoras = data.get('impresoras', [])
        tipo_etiqueta = data.get('tipo_etiqueta', 'auto')
        
        # Si viene una sola IP (test individual manual)
        if ip:
            command = data.get('command', '~HI')
            logging.info(f"🔍 Test Zebra individual {ip}: Comando={command}")
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                sock.connect((ip, 6101))
                sock.sendall(command.encode('utf-8'))
                response = sock.recv(1024).decode('utf-8', errors='ignore')
                sock.close()
                return jsonify({'success': True, 'response': response})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)}), 500
        
        # Si vienen varias impresoras (test por lotes)
        if not impresoras:
            return jsonify({'success': False, 'error': 'No hay impresoras o IP especificada'}), 400
            
        resultados = []
        for imp in impresoras:
            dept = imp.get('departamento')
            puesto = imp.get('puesto')
            
            if dept not in zebra_config or puesto not in zebra_config[dept]:
                resultados.append({
                    'puesto': f"{dept.upper()}-{puesto}", 
                    'departamento': dept,
                    'puesto_num': puesto,
                    'success': False, 
                    'error': 'No config'
                })
                continue
                
            ip_imp = zebra_config[dept][puesto]['ip']
            puerto = zebra_config[dept][puesto].get('puerto', 9100)
            # ✅ Obtener left_position de la configuración para determinar tamaño de etiqueta
            left_position = zebra_config[dept][puesto].get('left_position', 0)
            
            zpl = generar_zpl_test(dept, puesto, tipo_etiqueta, left_position=left_position)
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(4)
                s.connect((ip_imp, puerto))
                s.sendall(zpl.encode('utf-8'))
                s.close()
                resultados.append({
                    'puesto': f"{dept.upper()}-{puesto}", 
                    'departamento': dept,
                    'puesto_num': puesto,
                    'success': True
                })
            except Exception as e:
                resultados.append({
                    'puesto': f"{dept.upper()}-{puesto}", 
                    'departamento': dept,
                    'puesto_num': puesto,
                    'success': False, 
                    'error': str(e)
                })
                
        return jsonify({'success': True, 'resultados': resultados})
        
    except Exception as e:
        logging.error(f"❌ Error en test unificado: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/zebra/test-ip', methods=['POST'])
@login_required
def test_zebra_ip_directa():
    """Enviar test de impresión a una IP directa (sin necesidad de estar en BD)"""
    try:
        user = session['user']
        if user['rol'] != 'IT_ADMIN':
            return jsonify({'success': False, 'error': 'No autorizado'}), 403
        
        data = request.get_json()
        ip = data.get('ip', '').strip()
        
        if not ip:
            return jsonify({'success': False, 'error': 'IP requerida'}), 400
        
        # Primero leer left_position para determinar tipo de etiqueta
        left_position = 0  # default grande
        try:
            sock_query = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock_query.settimeout(3)
            sock_query.connect((ip, 6101))
            sock_query.sendall(b'! U1 getvar "zpl.left_position"\r\n')
            response = sock_query.recv(1024).decode('utf-8', errors='ignore').strip()
            sock_query.close()
            left_position = int(float(response.replace('"', '').strip()))
        except:
            logging.warning(f"⚠️ No se pudo leer left_position de {ip}, usando default 0")
        
        # Generar etiqueta según left_position
        tipo_etiqueta = 'pequena' if left_position < -100 else 'grande'
        zpl = generar_zpl_test('MANUAL', ip, tipo_etiqueta, left_position)
        
        # Enviar ZPL
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        sock.connect((ip, 9100))
        sock.sendall(zpl.encode('utf-8'))
        sock.close()
        
        logging.info(f"✅ Test enviado a IP directa: {ip} (tipo={tipo_etiqueta})")
        return jsonify({'success': True, 'message': f'Test enviado a {ip}', 'tipo': tipo_etiqueta})
        
    except socket.timeout:
        return jsonify({'success': False, 'error': f'Timeout conectando a {ip}'}), 500
    except Exception as e:
        logging.error(f"❌ Error test IP directa: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/zebra/config-ip', methods=['POST'])
@login_required
def config_zebra_ip_directa():
    """Configurar una impresora Zebra por IP directa (sin necesidad de estar en BD)"""
    try:
        user = session['user']
        if user['rol'] != 'IT_ADMIN':
            return jsonify({'success': False, 'error': 'No autorizado'}), 403
        
        data = request.get_json()
        ip = data.get('ip', '').strip()
        darkness = data.get('darkness')
        left_position = data.get('left_position')
        top_position = data.get('top_position')
        
        if not ip:
            return jsonify({'success': False, 'error': 'IP requerida'}), 400
        
        # Construir comandos SGD
        sgd_cmds = []
        
        if darkness is not None:
            val = max(0, min(30, int(darkness)))
            sgd_cmds.append(f'! U1 setvar "print.tone" "{val}"')
        
        if left_position is not None:
            sgd_cmds.append(f'! U1 setvar "zpl.left_position" "{int(left_position)}"')
        
        if top_position is not None:
            sgd_cmds.append(f'! U1 setvar "zpl.top_position" "{int(top_position)}"')
        
        if not sgd_cmds:
            return jsonify({'success': False, 'error': 'No hay parámetros para configurar'}), 400
        
        # Enviar comandos SGD
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect((ip, 6101))
        
        for cmd in sgd_cmds:
            sock.sendall((cmd + '\r\n').encode('utf-8'))
            time.sleep(0.2)
        
        sock.close()
        
        logging.info(f"✅ Configuración aplicada a IP {ip}: darkness={darkness}, left={left_position}, top={top_position}")
        return jsonify({'success': True, 'message': f'Configuración aplicada a {ip}'})
        
    except socket.timeout:
        return jsonify({'success': False, 'error': f'Timeout conectando a {ip}'}), 500
    except Exception as e:
        logging.error(f"❌ Error config IP directa: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/zebra/config/left-position', methods=['GET'])
@login_required
def config_left_position_real():
    """Configurar posición izquierda de forma masiva (Supervisor/Jefe Equipo/Admin)"""
    try:
        user = session['user']
        roles_permitidos = ['IT_ADMIN', 'SUPERVISOR', 'JEFE_EQUIPO', 'J. EQUIPO']
        if user['rol'] not in roles_permitidos:
            return jsonify({'success': False, 'error': 'No autorizado'}), 403
            
        data = request.get_json()
        impresoras = data.get('impresoras', []) # Lista de {departamento, puesto}
        left_position = data.get('left_position', 0)
        
        actualizadas = 0
        fallidas = 0
        
        for imp in impresoras:
            dept = imp.get('departamento')
            puesto = imp.get('puesto')
            
            if dept in zebra_config and puesto in zebra_config[dept]:
                config = zebra_config[dept][puesto]
                ip = config['ip']
                
                # 1. Actualizar BD
                mysql_db.actualizar_configuracion_zebra(
                    departamento=dept,
                    puesto=puesto,
                    left_position=left_position
                )
                
                # 2. Enviar SGD
                sgd_cmd = f'! U1 setvar "zpl.left_position" "{left_position}"\r\n'
                
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(3)
                    sock.connect((ip, 6101))
                    sock.sendall(sgd_cmd.encode('utf-8'))
                    sock.close()
                    actualizadas += 1
                    # Actualizar cache local
                    zebra_config[dept][puesto]['left_position'] = left_position
                except:
                    fallidas += 1
            else:
                fallidas += 1
                    
        return jsonify({
            'success': True,
            'total': len(impresoras),
            'actualizadas': actualizadas,
            'fallidas': fallidas
        })
    except Exception as e:
        logging.error(f"❌ Error configurando left position: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/zebra/verificar-y-corregir', methods=['GET'])
@login_required
def verificar_y_corregir_zebras_real():
    """
    Verificar y corregir automáticamente el contraste de las impresoras Zebra.
    Si el contraste no es 5 y la impresora NO está bloqueada, se corrige a 5.
    """
    try:
        user = session['user']
        if user['rol'] != 'IT_ADMIN':
            return jsonify({'success': False, 'error': 'No autorizado'}), 403
            
        departamento = request.args.get('departamento', '').lower()
        desde = request.args.get('desde', type=int)
        hasta = request.args.get('hasta', type=int)
        
        # Obtener configuraciones de la BD
        impresoras_db = mysql_db.get_zebras_configuracion(
            departamento=departamento if departamento else None,
            puesto_desde=desde,
            puesto_hasta=hasta
        )
        
        total = 0
        correctas = 0
        corregidas = 0
        con_issues = 0
        bloqueadas = 0
        issues = []
        
        for imp in impresoras_db:
            total += 1
            dept = imp['departamento']
            puesto = imp['puesto']
            ip = imp.get('ip')
            locked = imp.get('custom_locked', False)
            
            puesto_str = f"{dept.upper()}-{puesto}"
            
            if not ip:
                con_issues += 1
                issues.append({'puesto': puesto_str, 'problemas': 'IP no configurada', 'bloqueada': locked})
                continue
                
            # Intentar conectar y leer el contraste actual (print.tone)
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                sock.connect((ip, 6101))
                
                # Pedir el valor de print.tone
                sock.sendall(b'! U1 getvar "print.tone"\r\n')
                response = sock.recv(1024).decode('utf-8', errors='ignore').strip()
                sock.close()
                
                # Limpiar respuesta (a veces viene con comillas o espacios)
                current_tone = response.replace('"', '').strip()
                
                try:
                    # ✅ Manejar valores como "30.0" (convertir a float primero)
                    tone_val = int(float(current_tone))
                    if tone_val == 5:
                        correctas += 1
                    else:
                        if locked:
                            bloqueadas += 1
                            issues.append({
                                'puesto': puesto_str, 
                                'problemas': f'Contraste {tone_val} (Bloqueada)', 
                                'bloqueada': True,
                                'corregido': False
                            })
                        else:
                            # CORREGIR
                            try:
                                sock_fix = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                                sock_fix.settimeout(2)
                                sock_fix.connect((ip, 6101))
                                sock_fix.sendall(b'! U1 setvar "print.tone" "5"\r\n')
                                sock_fix.close()
                                corregidas += 1
                                issues.append({
                                    'puesto': puesto_str, 
                                    'problemas': f'Contraste {tone_val} → Corregido a 5', 
                                    'bloqueada': False,
                                    'corregido': True
                                })
                            except:
                                con_issues += 1
                                issues.append({
                                    'puesto': puesto_str, 
                                    'problemas': f'Error al corregir contraste {tone_val}', 
                                    'bloqueada': False,
                                    'corregido': False
                                })
                except:
                    con_issues += 1
                    issues.append({
                        'puesto': puesto_str, 
                        'problemas': f'Respuesta inválida: {response}', 
                        'bloqueada': locked
                    })
                    
            except socket.timeout:
                con_issues += 1
                issues.append({'puesto': puesto_str, 'problemas': 'Sin respuesta (timeout)', 'bloqueada': locked})
            except Exception as e:
                con_issues += 1
                issues.append({'puesto': puesto_str, 'problemas': f'Error: {str(e)}', 'bloqueada': locked})
                
        return jsonify({
            'success': True,
            'total': total,
            'correctas': correctas,
            'corregidas': corregidas,
            'con_issues': con_issues,
            'bloqueadas': bloqueadas,
            'issues': issues
        })
    except Exception as e:
        logging.error(f"❌ Error en verificar-y-corregir: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/reload-config', methods=['POST'])
@login_required
def reload_system_config():
    """Recargar todas las configuraciones desde MySQL (Máquinas, RFID, Zebras)
    
    Si se envía 'sync_printers': true, también lee los parámetros actuales de cada impresora
    física y actualiza la BD con los valores reales.
    """
    try:
        user = session['user']
        if user['rol'] != 'IT_ADMIN':
            return jsonify({'success': False, 'error': 'No autorizado'}), 403
        
        data = request.get_json() or {}
        sync_printers = data.get('sync_printers', True)  # Por defecto sincroniza
            
        logging.info(f"🔄 Recarga manual de configuración iniciada por {user['username']} (sync_printers={sync_printers})")
        
        # Recargar todo desde MySQL
        m_ok = load_machines_from_mysql()
        r_ok = load_rfid_from_mysql()
        z_ok = load_zebra_from_mysql()
        u_ok = update_active_users_from_db()
        
        # ✅ Si sync_printers está activo, leer parámetros reales de cada impresora
        sync_results = {'total': 0, 'ok': 0, 'failed': 0}
        if sync_printers and z_ok:
            sync_results = sincronizar_parametros_impresoras_reales()
        
        return jsonify({
            'success': True,
            'message': 'Configuraciones recargadas exitosamente',
            'status': {
                'machines': m_ok != False,
                'rfid': r_ok != False,
                'zebra': z_ok != False
            },
            'sync_printers': sync_results
        })
    except Exception as e:
        logging.error(f"❌ Error recargando configuraciones: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

def leer_parametros_impresora_real(ip):
    """
    Lee los parámetros actuales de una impresora Zebra vía SGD (puerto 6101).
    Retorna: dict con darkness, left_position o None si falla.
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        sock.connect((ip, 6101))
        
        # Leer print.tone (darkness) - escala 0-30
        sock.sendall(b'! U1 getvar "print.tone"\r\n')
        darkness_response = sock.recv(1024).decode('utf-8', errors='ignore').strip()
        try:
            darkness_str = darkness_response.replace('"', '').strip()
            # print.tone va de 0 a 30 directamente, no necesita conversión
            darkness = int(float(darkness_str))
        except ValueError:
            darkness = None
        
        # Leer left_position
        sock.sendall(b'! U1 getvar "zpl.left_position"\r\n')
        left_response = sock.recv(1024).decode('utf-8', errors='ignore').strip()
        try:
            left_str = left_response.replace('"', '').strip()
            left_position = int(float(left_str))
        except ValueError:
            left_position = None
        
        sock.close()
        
        return {
            'darkness': darkness,
            'left_position': left_position
        }
        
    except socket.timeout:
        logging.warning(f"⏱️ Timeout leyendo parámetros de {ip}:6101")
        return None
    except Exception as e:
        logging.warning(f"⚠️ Error leyendo parámetros de {ip}: {e}")
        return None

def sincronizar_parametros_impresoras_reales():
    """
    Conecta a todas las impresoras activas, lee sus parámetros reales
    y actualiza la base de datos.
    """
    global zebra_config
    
    total = 0
    ok = 0
    failed = 0
    
    logging.info("🔄 Iniciando sincronización de parámetros de impresoras...")
    
    for dept, puestos in zebra_config.items():
        for puesto, config in puestos.items():
            total += 1
            ip = config.get('ip')
            locked = config.get('custom_locked', False)
            
            if not ip:
                failed += 1
                continue
            
            # ⚠️ Si está bloqueada, solo leer pero NO actualizar BD
            params = leer_parametros_impresora_real(ip)
            
            if params:
                # ✅ Actualizar en memoria para mostrar en la tabla (siempre)
                if params['darkness'] is not None:
                    zebra_config[dept][puesto]['darkness_custom'] = params['darkness']
                if params['left_position'] is not None:
                    zebra_config[dept][puesto]['left_position'] = params['left_position']
                
                # ⚠️ Solo guardar en BD si NO está bloqueada
                if not locked:
                    try:
                        update_kwargs = {}
                        if params['darkness'] is not None:
                            update_kwargs['darkness_custom'] = params['darkness']
                        if params['left_position'] is not None:
                            update_kwargs['left_position'] = params['left_position']
                        
                        if update_kwargs:
                            mysql_db.actualizar_configuracion_zebra_parcial(
                                dept, puesto, **update_kwargs
                            )
                        logging.info(f"✅ {dept.upper()}-{puesto}: darkness={params['darkness']}, left={params['left_position']}")
                    except Exception as e:
                        logging.warning(f"⚠️ Error actualizando BD para {dept.upper()}-{puesto}: {e}")
                        failed += 1
                else:
                    logging.info(f"🔒 {dept.upper()}-{puesto}: Bloqueada, solo lectura")
                ok += 1
            else:
                failed += 1
    
    logging.info(f"📊 Sincronización completada: {ok}/{total} exitosas, {failed} fallidas")
    
    return {'total': total, 'ok': ok, 'failed': failed}

# =============================================================================
# ENDPOINTS API - GESTIÓN DE USUARIOS
# =============================================================================
@app.route('/api/usuarios', methods=['GET'])
@login_required
def get_usuarios():
    """Obtener lista de usuarios (solo IT_ADMIN) - Desde MySQL"""
    try:
        user = session['user']
        
        if user['rol'] != 'IT_ADMIN':
            return jsonify({
                'success': False,
                'error': 'No tienes permisos para esta acción'
            }), 403
        
        # ✅ OBTENER DESDE MySQL
        if not mysql_db:
            return jsonify({
                'success': False,
                'error': 'Sistema de usuarios no disponible'
            }), 503
        
        usuarios_lista = mysql_db.get_todos_usuarios()
        
        # Preparar respuesta (sin contraseñas)
        usuarios_respuesta = []
        for user_data in usuarios_lista:
            usuarios_respuesta.append({
                'username': user_data['username'],
                'nombre_completo': user_data['nombre_completo'],
                'rol': user_data['rol'],
                'departamento': user_data['departamento'],
                'activo': user_data['activo']
            })
        
        usuarios_respuesta.sort(key=lambda x: x['nombre_completo'])
        
        return jsonify({
            'success': True,
            'usuarios': usuarios_respuesta
        })
        
    except Exception as e:
        logging.error(f"❌ Error obteniendo usuarios: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/usuarios', methods=['POST'])
@login_required
def crear_usuario():
    """Crear nuevo usuario (solo IT_ADMIN) - Guarda en MySQL"""
    try:
        user = session['user']
        
        if user['rol'] != 'IT_ADMIN':
            return jsonify({
                'success': False,
                'error': 'No tienes permisos para esta acción'
            }), 403
        
        data = request.get_json()
        
        username = data.get('username', '').strip()
        if not username:
            return jsonify({'success': False, 'error': 'Username requerido'}), 400
        
        # ✅ VERIFICAR SI YA EXISTE EN MySQL
        if mysql_db.get_usuario_por_username(username):
            return jsonify({'success': False, 'error': 'El usuario ya existe'}), 400
        
        password = data.get('password', '').strip()
        if not password or len(password) < 4:
            return jsonify({'success': False, 'error': 'Contraseña debe tener al menos 5 caracteres'}), 400
        
        nombre_completo = data.get('nombre_completo', '').strip()
        if not nombre_completo:
            return jsonify({'success': False, 'error': 'Nombre completo requerido'}), 400
        
        rol = data.get('rol', '').strip()
        if rol not in ['IT_ADMIN', 'SUPERVISOR', 'OPERARIO', 'J. EQUIPO']:
            return jsonify({'success': False, 'error': 'Rol inválido'}), 400
        
        departamento = data.get('departamento', '').strip()
        if not departamento:
            return jsonify({'success': False, 'error': 'Departamento requerido'}), 400
        
        # ✅ CREAR EN MySQL
        nuevo_usuario = mysql_db.crear_usuario({
            'username': username,
            'password': password,
            'nombre_completo': nombre_completo,
            'rol': rol,
            'departamento': departamento
        })
        
        if not nuevo_usuario:
            return jsonify({
                'success': False,
                'error': 'Error guardando en base de datos'
            }), 500
        
        # ✅ RECARGAR CACHÉ DE USUARIOS
        load_users_from_mysql()
        
        logging.info(f"✅ Usuario creado: {username} por {user['username']}")
        
        return jsonify({
            'success': True,
            'message': f'Usuario {username} creado correctamente'
        })
        
    except Exception as e:
        logging.error(f"❌ Error creando usuario: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/usuarios/<username>', methods=['PUT'])
@login_required
def actualizar_usuario(username):
    """Actualizar estado de usuario (solo IT_ADMIN) - Actualiza en MySQL"""
    try:
        user = session['user']
        
        if user['rol'] != 'IT_ADMIN':
            return jsonify({
                'success': False,
                'error': 'No tienes permisos para esta acción'
            }), 403
        
        # ✅ VERIFICAR QUE EXISTE EN MySQL
        if not mysql_db.get_usuario_por_username(username):
            return jsonify({
                'success': False,
                'error': 'Usuario no encontrado'
            }), 404
        
        if username == user['username']:
            return jsonify({
                'success': False,
                'error': 'No puedes modificar tu propio usuario'
            }), 400
        
        data = request.get_json()
        activo = data.get('activo')
        
        if activo is None:
            return jsonify({
                'success': False,
                'error': 'Campo activo requerido'
            }), 400
        
        # ✅ ACTUALIZAR EN MySQL
        if not mysql_db.actualizar_estado_usuario(username, bool(activo)):
            return jsonify({
                'success': False,
                'error': 'Error actualizando en base de datos'
            }), 500
        
        # ✅ RECARGAR CACHÉ DE USUARIOS
        load_users_from_mysql()
        
        logging.info(f"✅ Usuario {username} {'activado' if activo else 'desactivado'} por {user['username']}")
        
        return jsonify({
            'success': True,
            'message': f'Usuario {username} {"activado" if activo else "desactivado"}'
        })
        
    except Exception as e:
        logging.error(f"❌ Error actualizando usuario: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/usuarios/<username>', methods=['DELETE'])
@login_required
def eliminar_usuario(username):
    """Eliminar usuario permanentemente (solo IT_ADMIN) - Elimina de MySQL"""
    try:
        user = session['user']
        
        if user['rol'] != 'IT_ADMIN':
            return jsonify({
                'success': False,
                'error': 'No tienes permisos para esta acción'
            }), 403
        
        # ✅ VERIFICAR QUE EXISTE EN MySQL
        usuario_existente = mysql_db.get_usuario_por_username(username)
        if not usuario_existente:
            return jsonify({
                'success': False,
                'error': 'Usuario no encontrado'
            }), 404
        
        if username == user['username']:
            return jsonify({
                'success': False,
                'error': 'No puedes eliminar tu propio usuario'
            }), 400
        
        # ✅ ELIMINAR DE MySQL
        if not mysql_db.eliminar_usuario(username):
            return jsonify({
                'success': False,
                'error': 'Error eliminando de base de datos'
            }), 500
        
        # ✅ RECARGAR CACHÉ DE USUARIOS
        load_users_from_mysql()
        
        logging.info(f"🗑️ Usuario ELIMINADO: {username} ({usuario_existente['nombre_completo']}) por {user['username']}")
        
        return jsonify({
            'success': True,
            'message': f'Usuario {username} eliminado permanentemente'
        })
        
    except Exception as e:
        logging.error(f"❌ Error eliminando usuario: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# =============================================================================
# ENDPOINTS API - RFID Y TEAMVIEWER
# =============================================================================
@app.route('/api/rfid/reboot', methods=['POST'])
@login_required
def rfid_reboot():
    """Reiniciar dispositivo RFID"""
    try:
        data = request.get_json()
        user = session['user']
        
        if user['rol'] != 'IT_ADMIN':
            return jsonify({
                'success': False,
                'error': 'No tienes permisos para esta acción'
            }), 403
        
        department = data['department'].lower()
        puesto = int(data['puesto'])
        
        if department not in rfid_config or puesto not in rfid_config[department]:
            return jsonify({
                'success': False,
                'error': f'No hay dispositivo RFID configurado para {department}-{puesto}'
            }), 404
        
        rfid_ip = rfid_config[department][puesto]
        success, message = ejecutar_ssh_reboot(rfid_ip, RFID_SSH_PASSWORD)
        
        logging.info(f"🔄 RFID reboot solicitado por {user['username']}: {department}-{puesto}")
        
        return jsonify({
            'success': success,
            'message': message,
            'rfid_ip': rfid_ip,
            'department': department,
            'puesto': puesto,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logging.error(f"❌ Error en RFID reboot: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/teamviewer/connect', methods=['POST'])
@login_required
def teamviewer_connect():
    """Registrar conexión TeamViewer"""
    try:
        data = request.get_json()
        ip = data.get('ip')
        user = session['user']
        
        logging.info(f"🖥️ TeamViewer solicitado por {user['username']} para IP: {ip}")
        
        return jsonify({
            'success': True,
            'message': 'TeamViewer abierto en cliente',
            'ip': ip,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logging.error(f"❌ Error en TeamViewer: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# =============================================================================
# ENDPOINTS API - ESTADO DEL SERVIDOR
# =============================================================================
@app.route('/api/status', methods=['GET'])
def status_endpoint():
    """Estado general del servidor (público)"""
    total_machines = sum(len(puestos) for puestos in machines_config.values())
    total_rfid = sum(len(puestos) for puestos in rfid_config.values())
    
    return jsonify({
        'status': 'online',
        'server_type': 'dashboard_control_logistico',
        'version': '2.4',
        'timestamp': datetime.now().isoformat(),
        'features': {
            'authentication': True,
            'database_integration': True,
            'teamviewer_support': True,
            'real_time_users': True,
            'rfid_reboot': True,
            'incident_management': True,
            'ret_to_pack_vas_mapping': True
        },
        'machines_info': {
            'total_loaded': total_machines,
            'departments': list(machines_config.keys()),
            'active_users': len(active_users_cache),
            'rfid_devices': total_rfid
        }
    })

# =============================================================================
# ENDPOINTS API - ANALYTICS (mantener existentes)
# =============================================================================
from collections import Counter, defaultdict
from datetime import timedelta


# =============================================================================
# ENDPOINTS API - CONFIGURACIONES (IT_ADMIN ONLY)
# =============================================================================

@app.route('/api/config/rfid/reboot-masivo', methods=['POST'])
@login_required
def reboot_rfid_masivo():
    """Reiniciar RFIDs masivamente (solo IT_ADMIN)"""
    try:
        user = session['user']
        if user['rol'] != 'IT_ADMIN':
            return jsonify({'success': False, 'error': 'No autorizado'}), 403
        
        data = request.get_json()
        departamento = data.get('departamento', 'todos')
        desde = data.get('desde', 1)
        hasta = data.get('hasta', 100)
        filtro = data.get('filter', 'all')  # 'all', 'odd', 'even'
        
        total = 0
        exitosos = 0
        fallidos = 0
        
        # Determinar qué departamentos procesar
        departamentos = []
        if departamento == 'todos':
            departamentos = ['packing', 'return', 'vas']
        else:
            departamentos = [departamento]
        
        for dept in departamentos:
            if dept not in rfid_config:
                continue
                
            for puesto in range(desde, hasta + 1):
                # Aplicar filtro de paridad
                if filtro == 'odd' and puesto % 2 == 0: continue
                if filtro == 'even' and puesto % 2 != 0: continue
                
                if puesto in rfid_config[dept]:
                    total += 1
                    rfid_ip = rfid_config[dept][puesto]
                    success, mensaje = ejecutar_ssh_reboot(rfid_ip, RFID_SSH_PASSWORD)
                    
                    if success:
                        exitosos += 1
                        logging.info(f"✅ RFID reiniciado masivamente: {dept.upper()}-{puesto} ({rfid_ip})")
                    else:
                        fallidos += 1
                        logging.warning(f"⚠️ Fallo reinicio masivo: {dept.upper()}-{puesto} ({rfid_ip}): {mensaje}")
        
        logging.info(f"📊 Reinicio masivo RFID completado por {user['username']}: {exitosos}/{total} exitosos (filtro: {filtro})")
        
        return jsonify({
            'success': True,
            'total': total,
            'exitosos': exitosos,
            'fallidos': fallidos
        })
        
    except Exception as e:
        logging.error(f"❌ Error en reinicio masivo RFID: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/config/zebra/aplicar-masivo', methods=['POST'])
@login_required
def aplicar_config_zebra_masivo():
    """Aplicar configuración masiva a impresoras Zebra (solo IT_ADMIN)"""
    try:
        user = session['user']
        if user['rol'] != 'IT_ADMIN':
            return jsonify({'success': False, 'error': 'No autorizado'}), 403
        
        data = request.get_json()
        departamento = data.get('departamento', 'todos')
        desde = data.get('desde', 1)
        hasta = data.get('hasta', 100)
        darkness = data.get('darkness')
        left_position = data.get('left_position')
        top_position = data.get('top_position')
        locked = data.get('locked', False)
        filtro = data.get('filtro', 'todos')
        disable_sleep = data.get('disable_sleep', False)
        
        total = 0
        exitosos = 0
        fallidos = 0
        
        departamentos = []
        if departamento == 'todos':
            departamentos = ['packing', 'return', 'vas']
        else:
            departamentos = [departamento]
        
        for dept in departamentos:
            for puesto in range(desde, hasta + 1):
                if filtro == 'pares' and puesto % 2 != 0:
                    continue
                if filtro == 'impares' and puesto % 2 == 0:
                    continue
                    
                total += 1
                
                # 1. Actualizar en base de datos
                db_success = mysql_db.actualizar_configuracion_zebra(
                    departamento=dept,
                    puesto=puesto,
                    darkness_custom=darkness,
                    left_position=left_position,
                    top_position=top_position,
                    custom_locked=locked
                )
                
                # 2. Enviar comandos SGD a la impresora física
                ip = None
                if dept in zebra_config and str(puesto) in zebra_config[dept]:
                    ip = zebra_config[dept][str(puesto)].get('ip')
                elif dept in zebra_config and puesto in zebra_config[dept]:
                    ip = zebra_config[dept][puesto].get('ip')
                
                sgd_success = False
                if ip:
                    try:
                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock.settimeout(5)
                        sock.connect((ip, 6101))
                        
                        # Enviar comandos SGD
                        if darkness is not None:
                            cmd = f'! U1 setvar "print.tone" "{int(darkness)}"\r\n'
                            sock.sendall(cmd.encode('utf-8'))
                            time.sleep(0.2)
                        
                        if left_position is not None:
                            cmd = f'! U1 setvar "zpl.left_position" "{int(left_position)}"\r\n'
                            sock.sendall(cmd.encode('utf-8'))
                            time.sleep(0.2)
                        
                        if top_position is not None:
                            cmd = f'! U1 setvar "zpl.top_position" "{int(top_position)}"\r\n'
                            sock.sendall(cmd.encode('utf-8'))
                            time.sleep(0.2)
                        
                        if disable_sleep:
                            cmd = '! U1 setvar "power.dpm.enable" "off"\r\n'
                            sock.sendall(cmd.encode('utf-8'))
                        
                        sock.close()
                        sgd_success = True
                        logging.info(f"✅ Zebra configurada: {dept.upper()}-{puesto} (darkness={darkness}, left={left_position})")
                    except Exception as e:
                        logging.warning(f"⚠️ Error enviando SGD a {dept.upper()}-{puesto} ({ip}): {e}")
                else:
                    logging.warning(f"⚠️ No hay IP para {dept.upper()}-{puesto}")
                
                if db_success and sgd_success:
                    exitosos += 1
                elif db_success or sgd_success:
                    exitosos += 1  # Parcialmente exitoso
                else:
                    fallidos += 1
        
        logging.info(f"📊 Configuración masiva Zebra por {user['username']}: {exitosos}/{total} exitosos")
        
        return jsonify({
            'success': True,
            'total': total,
            'exitosos': exitosos,
            'fallidos': fallidos
        })
        
    except Exception as e:
        logging.error(f"❌ Error aplicando configuración masiva Zebra: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/config/zebra/restaurar-defaults', methods=['POST'])
@login_required
def restaurar_defaults_zebra():
    """Restaurar configuración predeterminada de Zebras (solo IT_ADMIN)"""
    try:
        user = session['user']
        if user['rol'] != 'IT_ADMIN':
            return jsonify({'success': False, 'error': 'No autorizado'}), 403
        
        data = request.get_json()
        departamento = data.get('departamento', 'todos')
        desde = data.get('desde', 1)
        hasta = data.get('hasta', 100)
        
        total = 0
        exitosos = 0
        
        # Determinar qué departamentos procesar
        departamentos = []
        if departamento == 'todos':
            departamentos = ['packing', 'return', 'vas']
        else:
            departamentos = [departamento]
        
        for dept in departamentos:
            # Definir valores predeterminados según departamento
            left_default = 0 if dept == 'packing' else -215
            
            for puesto in range(desde, hasta + 1):
                total += 1
                
                # Restaurar a valores predeterminados y desbloquear
                success = mysql_db.actualizar_configuracion_zebra(
                    departamento=dept,
                    puesto=puesto,
                    darkness_custom=None,  # Usar default (5)
                    left_position=left_default,
                    top_position=0,
                    custom_locked=False  # Desbloquear
                )
                
                if success:
                    exitosos += 1
                    logging.info(f"✅ Zebra restaurada a defaults: {dept.upper()}-{puesto}")
        
        logging.info(f"📊 Restauración defaults Zebra por{user['username']}: {exitosos}/{total}")
        
        return jsonify({
            'success': True,
            'total': total,
            'exitosos': exitosos
        })
        
    except Exception as e:
        logging.error(f"❌ Error restaurando defaults Zebra: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/config/zebra/verificar', methods=['GET'])
@login_required
def verificar_config_zebra():
    """Verificar configuraciones de impresoras Zebra (solo IT_ADMIN)"""
    try:
        user = session['user']
        if user['rol'] != 'IT_ADMIN':
            return jsonify({'success': False, 'error': 'No autorizado'}), 403
        
        departamento = request.args.get('departamento')
        desde = request.args.get('desde', type=int)
        hasta = request.args.get('hasta', type=int)
        
        impresoras = mysql_db.get_zebras_configuracion(departamento=departamento,puesto_desde=desde,puesto_hasta=hasta)
        
        total = len(impresoras)
        correctas = 0
        issues = []
        bloqueadas = 0
        
        for imp in impresoras:
            dept = imp['departamento']
            puesto = imp['puesto']
            ip = imp['ip']
            
            if imp.get('custom_locked'):
                bloqueadas += 1
            
            # Leer valores REALES de la impresora
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3)
                sock.connect((ip, 6101))
                
                # Consultar darkness real
                sock.sendall(b'! U1 getvar "print.tone"\r\n')
                darkness_real = sock.recv(1024).decode().strip()
                
                # Consultar left position real
                sock.sendall(b'! U1 getvar "zpl.left_position"\r\n')
                left_real = sock.recv(1024).decode().strip()
                
                sock.close()
                
                # Comparar con lo esperado
                darkness_esperado = imp.get('darkness_custom') or 5
                left_esperado = imp.get('left_position') or (0 if dept=='packing' else -215)
                
                problemas = []
                if darkness_real and int(darkness_real) != darkness_esperado:
                    problemas.append(f"Contraste real:{darkness_real} esperado:{darkness_esperado}")
                if left_real and int(left_real) != left_esperado:
                    problemas.append(f"Pos.Izq real:{left_real} esperado:{left_esperado}")
                
                if problemas:
                    issues.append({'puesto':f"{dept.upper()}-{puesto}",'ip':ip,'problemas':' | '.join(problemas),'bloqueada':imp.get('custom_locked')})
                else:
                    correctas += 1
                    
            except Exception as e:
                issues.append({'puesto':f"{dept.upper()}-{puesto}",'ip':ip,'problemas':f"Error conexión: {str(e)}",'bloqueada':imp.get('custom_locked')})
        
        return jsonify({
            'success': True,
            'total': total,
            'correctas': correctas,
            'con_issues': len(issues),
            'bloqueadas': bloqueadas,
            'issues': issues
        })
        
    except Exception as e:
        logging.error(f"❌ Error verificando configuraciones Zebra: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

# =============================================================================
# FUNCIÓN TEST IMPRESORAS - GENERAR ETIQUETAS DE PRUEBA
# =============================================================================

def enviar_test_impresora(ip, departamento, puesto, puerto=9100):
    """
    Envía una etiqueta de test a la impresora Zebra.
    
    Args:
        ip (str): IP de la impresora
        departamento (str): departamento (packing, return, vas)
        puesto (int): número de puesto
        puerto (int): puerto de la impresora (default 9100)
        
    Returns:
        tuple: (success: bool, mensaje: str)
    """
    sock = None
    try:
        # LEER LEFT_POSITION DIRECTAMENTE DE LA IMPRESORA (estado real)
        # left_position >= -100 -> etiqueta grande (10x15cm)
        # left_position < -100 -> etiqueta pequeña (6x3cm)
        left_position = None
        tipo_imp = 'grande'  # Default
        
        try:
            # Conectarse al puerto SGD (6101) para obtener configuración REAL
            logging.info(f"🔌 Leyendo left_position real de {departamento.upper()}-{puesto} ({ip}:6101)...")
            sock_query = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock_query.settimeout(3)
            sock_query.connect((ip, 6101))
            
            # Consultar left_position real
            sock_query.sendall(b'! U1 getvar "zpl.left_position"\r\n')
            response = sock_query.recv(1024).decode('utf-8', errors='ignore').strip()
            sock_query.close()
            
            # Limpiar respuesta y convertir a número
            left_position_str = response.replace('"', '').strip()
            try:
                left_position = int(float(left_position_str))
                logging.info(f"📊 left_position REAL desde impresora: {left_position}")
            except ValueError:
                logging.warning(f"⚠️ Respuesta inesperada de impresora: '{response}' - usando default")
                left_position = None
                
        except socket.timeout:
            logging.warning(f"⏱️ Timeout leyendo left_position de {ip}:6101 - usando default")
        except Exception as e:
            logging.warning(f"⚠️ Error leyendo left_position de {ip}: {e} - usando default")
        
        # Fallback: Si no se pudo leer de la impresora, usar defaults inteligentes
        if left_position is None:
            left_position = 0 if departamento == 'packing' else -215
            logging.info(f"🔧 left_position por defecto: {left_position}")
        
        # Decidir tipo de etiqueta según left_position REAL
        if left_position < -100:
            tipo_imp = 'pequena'
        else:
            tipo_imp = 'grande'
        
        logging.info(f"🏷️ Tipo etiqueta para {departamento.upper()}-{puesto}: {tipo_imp} (left_position={left_position})")

        zpl = generar_zpl_test(departamento, puesto, tipo_imp)
        
        logging.info(f"🖨️ Enviando etiqueta test a {departamento.upper()}-{puesto} ({ip}:{puerto})")
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        
        sock.connect((ip, puerto))
        sock.sendall(zpl.encode('utf-8'))
        sock.close()
        
        logging.info(f"✅ Test enviado correctamente a {departamento.upper()}-{puesto}")
        return True, f"Test enviado a {departamento.upper()}-{puesto}"
        
    except socket.timeout:
        error_msg = f"Timeout conectando a {ip}:{puerto}"
        logging.error(f"❌ {error_msg}")
        return False, error_msg
    except socket.error as e:
        error_msg = f"Error de conexión: {str(e)}"
        logging.error(f"❌ {error_msg}")
        return False, error_msg
    except Exception as e:
        error_msg = f"Error inesperado: {str(e)}"
        logging.error(f"❌ {error_msg}")
        return False, error_msg
    finally:
        try:
            if sock:
                sock.close()
        except:
            pass


# =============================================================================
# ENDPOINT TEST IMPRESORAS
# =============================================================================

@app.route('/api/zebra/bloqueadas', methods=['GET'])
@login_required
def get_zebras_bloqueadas():
    try:
        user = session['user']
        if user['rol'] != 'IT_ADMIN':
            return jsonify({'success': False, 'error': 'No autorizado'}), 403
        bloqueadas = mysql_db.get_zebras_bloqueadas()
        return jsonify({'success': True, 'total': len(bloqueadas), 'impresoras': bloqueadas})
    except Exception as e:
        logging.error(f"❌ Error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/zebra/desbloquear', methods=['POST'])
@login_required
def desbloquear_zebras():
    try:
        user = session['user']
        if user['rol'] != 'IT_ADMIN':
            return jsonify({'success': False, 'error': 'No autorizado'}), 403
        data = request.get_json()
        impresoras = data.get('impresoras', [])
        if not impresoras:
            return jsonify({'success': False, 'error': 'No se especificaron impresoras'}), 400
        exitosas = 0
        fallidas = 0
        for imp in impresoras:
            if mysql_db.desbloquear_zebra(imp.get('departamento'), imp.get('puesto')):
                exitosas += 1
            else:
                fallidas += 1
        return jsonify({'success': True, 'total': len(impresoras), 'exitosas': exitosas, 'fallidas': fallidas})
    except Exception as e:
        logging.error(f"❌ Error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/zebra/config/lista', methods=['GET'])
@login_required
def get_lista_configuraciones():
    try:
        user = session['user']
        if user['rol'] != 'IT_ADMIN':
            return jsonify({'success': False, 'error': 'No autorizado'}), 403
        departamento = request.args.get('departamento')
        impresoras = mysql_db.get_zebras_configuracion(departamento=departamento)
        return jsonify({'success': True, 'total': len(impresoras), 'impresoras': impresoras})
    except Exception as e:
        logging.error(f"❌ Error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/zebra/config/left-position', methods=['POST'])
@login_required
def config_left_position_supervisor():
    """Configurar posición izquierda de impresoras - PARA SUPERVISOR/JEFE_EQUIPO"""
    try:
        user = session['user']
        if user['rol'] not in ['IT_ADMIN', 'SUPERVISOR', 'JEFE_EQUIPO', 'J. EQUIPO']:
            return jsonify({'success': False, 'error': 'No autorizado'}), 403
            
        data = request.get_json()
        impresoras = data.get('impresoras', [])
        left_position = data.get('left_position', 0)
        
        logging.info(f"📐 Ajuste de margen por {user['username']} a {left_position} para {len(impresoras)} impresoras")
        
        actualizadas = 0
        fallidas = 0
        
        for imp in impresoras:
            dept = imp.get('departamento', '').lower()
            try:
                puesto = int(imp.get('puesto', 0))
            except:
                puesto = 0
            
            # 1. Actualizar en BD
            if mysql_db.actualizar_configuracion_zebra_parcial(dept, puesto, left_position=left_position):
                # 2. Enviar comando a la impresora si está en cache
                ip = None
                if dept in zebra_config and puesto in zebra_config[dept]:
                    ip = zebra_config[dept][puesto].get('ip')
                
                if ip:
                    try:
                        # Comando SGD para posición izquierda
                        zpl = f'! U1 setvar "device.languages" "zpl"\r\n! U1 setvar "zpl.left_position" "{left_position}"\r\n'
                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock.settimeout(3)
                        sock.connect((ip, 6101))
                        sock.sendall(zpl.encode('utf-8'))
                        sock.close()
                        actualizadas += 1
                        logging.info(f"✅ Margen ajustado en {dept.upper()}-{puesto} ({ip})")
                    except Exception as e:
                        logging.warning(f"⚠️ No se pudo enviar comando a {dept}-{puesto} ({ip}): {str(e)}")
                        fallidas += 1
                else:
                    logging.warning(f"⚠️ No hay IP cacheada para {dept.upper()}-{puesto} (se actualizó solo BD)")
                    actualizadas += 1 
            else:
                fallidas += 1
                
        return jsonify({
            'success': True,
            'actualizadas': actualizadas,
            'fallidas': fallidas,
            'left_position': left_position
        })
    except Exception as e:
        logging.error(f"❌ Error en config left position: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

def worker_chequeo_impresoras():
    import time
    import socket
    logging.info("🔄 Worker chequeo impresoras iniciado (Intervalo: 300s)")
    while True:
        try:
            time.sleep(300) # 5 minutos
            if not mysql_db:
                continue
            
            impresoras = mysql_db.get_todas_zebra(activas_solo=True)
            if not impresoras:
                continue
                
            logging.info(f"🔎 Worker: Revisando contraste de {len(impresoras)} impresoras...")
            corregidas = 0
            left_corregidas = 0
            
            for imp in impresoras:
                try:
                    dept = imp['departamento']
                    puesto = imp['puesto']
                    ip = imp.get('ip')
                    locked = imp.get('custom_locked', False)
                    
                    if not ip or locked:
                        continue
                        
                    # 1. VERIFICAR CONTRASTE REAL
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(3)
                    sock.connect((ip, 6101))
                    
                    sock.sendall(b'! U1 getvar "print.tone"\r\n')
                    response = sock.recv(1024).decode('utf-8', errors='ignore').strip()
                    sock.close()
                    
                    # Limpiar respuesta
                    current_tone = response.replace('"', '').strip()
                    try:
                        tone_val = int(float(current_tone))
                    except:
                        continue
                        
                    # 2. CORREGIR CONTRASTE SI ES NECESARIO
                    target_tone = imp.get('darkness_custom')
                    if target_tone is None:
                        target_tone = 5
                        
                    if tone_val != target_tone:
                        logging.info(f"⚠️ Contraste incorrecto en {dept.upper()}-{puesto}: real={tone_val}, target={target_tone} -> Corrigiendo")
                        
                        sock_fix = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock_fix.settimeout(3)
                        sock_fix.connect((ip, 6101))
                        cmd = f'! U1 setvar "print.tone" "{target_tone}"\r\n'
                        sock_fix.sendall(cmd.encode('utf-8'))
                        sock_fix.close()
                        
                        corregidas += 1
                        
                        # Si corregimos algo que no estaba en BD (ej. null), lo guardamos
                        if imp.get('darkness_custom') is None:
                             mysql_db.actualizar_configuracion_zebra_parcial(dept, puesto, darkness_custom=5)
                    
                    # 3. VERIFICAR LEFT_POSITION
                    # Valores válidos: 0 y -215 (no tocar)
                    # Cualquier otro valor (ej: 20) -> corregir a 0
                    VALID_LEFT_POSITIONS = [0, -215]
                    
                    sock_left = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock_left.settimeout(3)
                    sock_left.connect((ip, 6101))
                    sock_left.sendall(b'! U1 getvar "zpl.left_position"\r\n')
                    left_response = sock_left.recv(1024).decode('utf-8', errors='ignore').strip()
                    sock_left.close()
                    
                    try:
                        current_left = int(float(left_response.replace('"', '').strip()))
                    except:
                        current_left = None
                    
                    # 4. CORREGIR LEFT_POSITION SI NO ES UN VALOR VÁLIDO
                    if current_left is not None and current_left not in VALID_LEFT_POSITIONS:
                        logging.info(f"⚠️ Left_position incorrecto en {dept.upper()}-{puesto}: real={current_left} -> Corrigiendo a 0")
                        
                        sock_fix_left = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock_fix_left.settimeout(3)
                        sock_fix_left.connect((ip, 6101))
                        cmd_left = f'! U1 setvar "zpl.left_position" "0"\r\n'
                        sock_fix_left.sendall(cmd_left.encode('utf-8'))
                        sock_fix_left.close()
                        
                        left_corregidas += 1
                        mysql_db.actualizar_configuracion_zebra_parcial(dept, puesto, left_position=0)
                        
                except Exception as e_imp:
                    # Silenciar errores individuales para no llenar logs
                    pass
            
            if corregidas > 0 or left_corregidas > 0:
                logging.info(f"✅ Worker: {corregidas} contrastes y {left_corregidas} left_position corregidos")
                
        except Exception as e:
            logging.error(f"❌ Worker error: {str(e)}")

import threading
worker_thread = threading.Thread(target=worker_chequeo_impresoras, daemon=True)
worker_thread.start()

# =============================================================================
# PROGRAMACIÓN DE REINICIO AUTOMÁTICO DE RFID
# =============================================================================

# Configuración de programación RFID (se carga desde archivo JSON)
rfid_schedule_config = {
    'enabled': False,
    'days': [],  # 0=Dom, 1=Lun, 2=Mar, 3=Mié, 4=Jue, 5=Vie, 6=Sáb
    'time': '23:00'
}

def cargar_config_rfid_schedule():
    """Cargar configuración de programación RFID desde archivo"""
    global rfid_schedule_config
    config_path = os.path.join(os.path.dirname(__file__), 'rfid_schedule.json')
    try:
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                rfid_schedule_config = json.load(f)
            logging.info(f"✅ Configuración RFID schedule cargada: {rfid_schedule_config}")
    except Exception as e:
        logging.warning(f"⚠️ Error cargando rfid_schedule.json: {e}")

def guardar_config_rfid_schedule():
    """Guardar configuración de programación RFID a archivo"""
    config_path = os.path.join(os.path.dirname(__file__), 'rfid_schedule.json')
    try:
        with open(config_path, 'w') as f:
            json.dump(rfid_schedule_config, f, indent=2)
        logging.info(f"✅ Configuración RFID schedule guardada")
    except Exception as e:
        logging.error(f"❌ Error guardando rfid_schedule.json: {e}")

# Cargar configuración al iniciar
cargar_config_rfid_schedule()

@app.route('/api/rfid/schedule', methods=['GET'])
@login_required
def get_rfid_schedule():
    """Obtener configuración de programación de reinicio RFID"""
    try:
        return jsonify({
            'success': True,
            'schedule': rfid_schedule_config
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/rfid/schedule', methods=['POST'])
@login_required
def set_rfid_schedule():
    """Guardar configuración de programación de reinicio RFID"""
    try:
        user = session['user']
        if user['rol'] != 'IT_ADMIN':
            return jsonify({'success': False, 'error': 'No autorizado'}), 403
        
        global rfid_schedule_config
        data = request.get_json()
        
        rfid_schedule_config = {
            'enabled': data.get('enabled', False),
            'days': data.get('days', []),
            'time': data.get('time', '23:00')
        }
        
        guardar_config_rfid_schedule()
        
        logging.info(f"📅 Programación RFID actualizada por {user['username']}: {rfid_schedule_config}")
        return jsonify({'success': True, 'message': 'Programación guardada'})
        
    except Exception as e:
        logging.error(f"❌ Error guardando schedule RFID: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

def worker_rfid_schedule():
    """Worker que verifica y ejecuta reinicios programados de RFID"""
    import datetime
    import time as time_module
    last_executed_date = None
    
    while True:
        try:
            if not rfid_schedule_config.get('enabled', False):
                time_module.sleep(60)
                continue
            
            now = datetime.datetime.now()
            current_day = now.weekday()  # 0=Lunes en Python
            # Convertir a formato JS (0=Domingo)
            js_day = (current_day + 1) % 7
            
            config_time = rfid_schedule_config.get('time', '23:00')
            try:
                config_hour, config_min = map(int, config_time.split(':'))
            except:
                config_hour, config_min = 23, 0
            
            # Verificar si es el día y hora correctos
            if js_day in rfid_schedule_config.get('days', []):
                if now.hour == config_hour and now.minute == config_min:
                    # Evitar ejecutar más de una vez por día
                    today_str = now.strftime('%Y-%m-%d')
                    if last_executed_date != today_str:
                        last_executed_date = today_str
                        logging.info(f"🔄 INICIANDO REINICIO PROGRAMADO DE RFID (Config: {config_time})")
                        
                        # Recargar dispositivos de la BD para asegurar que están actualizados
                        load_rfid_from_mysql()
                        
                        count_ok = 0
                        count_error = 0
                        
                        # Iterar por todos los departamentos y puestos en rfid_config
                        for dept, puestos in rfid_config.items():
                            for puesto_num, ip in puestos.items():
                                try:
                                    success, msg = ejecutar_ssh_reboot(ip)
                                    if success:
                                        logging.info(f"✅ RFID {dept.upper()}-{puesto_num} ({ip}) reiniciado")
                                        count_ok += 1
                                    else:
                                        logging.warning(f"⚠️ Error reiniciando RFID {dept.upper()}-{puesto_num} ({ip}): {msg}")
                                        count_error += 1
                                    time_module.sleep(0.5)  # Pausa para no saturar
                                except Exception as e:
                                    logging.error(f"❌ Error en bucle reinicio {dept}-{puesto_num}: {e}")
                                    count_error += 1
                        
                        logging.info(f"🏁 FIN REINICIO PROGRAMADO: {count_ok} OK, {count_error} FALLIDOS")
            
            time_module.sleep(60) # Esperar al siguiente minuto
            
        except Exception as e:
            logging.error(f"❌ Error en worker RFID schedule: {e}")
            time_module.sleep(60)

# Iniciar worker de programación RFID
rfid_schedule_thread = threading.Thread(target=worker_rfid_schedule, daemon=True)
rfid_schedule_thread.start()


@app.route('/api/zebra/test-ui', methods=['POST'])
@login_required
def test_zebras_con_validacion():
    try:
        user = session['user']
        if user['rol'] != 'IT_ADMIN':
            return jsonify({'success': False, 'error': 'No autorizado'}), 403
        data = request.get_json()
        resultados_test = data.get('resultados', [])
        incidencias_creadas = []
        errores = []
        for resultado in resultados_test:
            if resultado.get('estado') == 'mal':
                try:
                    dept = resultado.get('departamento') or 'packing'
                    puesto = resultado.get('puesto') or '0'
                    observaciones = resultado.get('observaciones', '').strip()
                    if not observaciones:
                        observaciones = 'Cabezal térmico posiblemente dañado o consumido'
                    
                    # Asegurar que puesto es un número
                    try:
                        puesto_num = int(puesto)
                    except:
                        puesto_num = 0
                    
                    logging.info(f"📋 Creando incidencia para {dept.upper()}-{puesto_num}: {observaciones}")
                    
                    datos_incidencia = {
                        'departamento': dept.lower(),
                        'puesto': puesto_num,  # Pasar como número directamente
                        'categoria': 'IMPRESORA_ZEBRA',
                        'descripcion': f"Test de impresora falló. {observaciones}",
                        'prioridad': 'media'
                    }
                    
                    logging.info(f"📦 Datos: {datos_incidencia}")
                    
                    nueva_inc = mysql_db.crear_incidencia(
                        datos=datos_incidencia,
                        reportado_por_nombre='Sistema - Test Automático',
                        reportado_por_username='auto_test'
                    )
                    
                    if nueva_inc:
                        logging.info(f"✅ Incidencia creada: {nueva_inc.get('id')}")
                        incidencias_creadas.append(nueva_inc.get('id'))
                    else:
                        logging.warning(f"⚠️ mysql_db.crear_incidencia retornó None para {dept.upper()}-{puesto_num}")
                        errores.append(f"{dept.upper()}-{puesto_num}")
                except Exception as e:
                    logging.error(f"❌ Excepción creando incidencia: {str(e)}")
                    errores.append(str(e))
        
        logging.info(f"📊 Total incidencias creadas: {len(incidencias_creadas)}, errores: {len(errores)}")
        return jsonify({
            'success': True, 
            'incidencias_creadas': len(incidencias_creadas), 
            'ids': incidencias_creadas,
            'errores': errores
        })
    except Exception as e:
        logging.error(f"❌ Error general: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

def generar_zpl_test(dept, puesto, tipo_etiqueta='auto', left_position=None):
    """
    Genera ZPL para etiqueta de test.
    - Grande (Packing): 10x15cm (800x1200 dots)
    - Pequeña (Return/VAS): 6x3cm (480x240 dots)
    Diseño: Franja negra limpia arriba, puesto, separador, instrucciones, fecha.
    
    IMPORTANTE: En modo 'auto', determina el tamaño basándose en left_position:
    - left_position = 0 o 20 → etiqueta grande
    - left_position = -215 → etiqueta pequeña
    """
    from datetime import datetime
    ahora = datetime.now().strftime('%d/%m/%Y %H:%M')
    
    # Generar prefijo corto para el puesto
    dept_lower = dept.lower()
    if dept_lower == 'packing':
        prefijo = 'PACK'
    elif dept_lower == 'return':
        prefijo = 'RET'
    elif dept_lower == 'vas':
        prefijo = 'VAS'
    else:
        prefijo = dept.upper()[:4]
    
    puesto_completo = f"{prefijo}-{puesto}"
    
    usar_grande = False
    if tipo_etiqueta == 'grande':
        usar_grande = True
    elif tipo_etiqueta == 'pequena':
        usar_grande = False
    else:  # auto - determinar por left_position
        if left_position is not None:
            # Si left_position es -215 (o muy negativo), usar etiqueta pequeña
            # Si es 0 o positivo (como 20), usar etiqueta grande
            usar_grande = (left_position >= -50)  # -215 es pequeña, 0/20 es grande
            logging.info(f"🏷️ Test {puesto_completo}: left_position={left_position} → {'grande' if usar_grande else 'pequeña'}")
        else:
            # Fallback al departamento si no hay left_position
            usar_grande = (dept_lower == 'packing')

    if usar_grande:
        # --- ETIQUETA GRANDE (100x150mm) ---
        return f"""^XA
^CI28^LL1200^PW832^LS0

^FO0,0^GB850,180,180^FS

^CF0,140
^FO0,350^FB832,1,0,C^FD{puesto_completo}^FS

^FO50,700^GB732,8,8^FS

^CF0,65
^FO0,780^FB832,1,0,C^FDENTREGAR A KEY USER^FS
^CF0,80
^FO0,880^FB832,1,0,C^FDNO TIRAR^FS

^CF0,50
^FO0,1050^FB832,1,0,C^FD{ahora}^FS
^XZ"""

    else:
        # --- ETIQUETA PEQUEÑA (60x30mm) ---
        # Reajustado: PW 480 (60mm), LL 240 (30mm), LS -215
        # Centrado en 480 dots para evitar desbordamiento
        return f"""^XA
^CI28^LL240^PW480^LS-215

^FO0,0^GB480,60,60^FS

^CF0,50
^FO0,75^FB480,1,0,C^FD{puesto_completo}^FS

^FO20,135^GB440,3,3^FS

^CF0,26
^FO0,155^FB480,1,0,C^FDENTREGAR A KEY USER^FS
^CF0,30
^FO0,190^FB480,1,0,C^FDNO TIRAR^FS

^CF0,20
^FO0,225^FB480,1,0,C^FD{ahora}^FS
^XZ"""


@app.route('/api/chequeo/guardar',methods=['POST'])
@login_required
def guardar_chequeo():
    try:
        user=session['user']
        if user['rol']!='IT_ADMIN':
            return jsonify({'success':False,'error':'No autorizado'}),403
        data=request.get_json()
        chequeo_id=mysql_db.crear_chequeo_general({'departamento':data['departamento'],'puesto':data['puesto'],'usuario_id':user.get('id'),'usuario_nombre':user['nombre_completo']})
        if chequeo_id:
            for comp in ['pantalla','ordenador','teclado_cherry','pistola','impresora','raton','cognex','rfid']:
                if comp in data:
                    mysql_db.actualizar_componente_chequeo(chequeo_id,comp,data[comp])
            mysql_db.finalizar_chequeo(chequeo_id,data.get('observaciones',''))
            return jsonify({'success':True,'id':chequeo_id})
        return jsonify({'success':False,'error':'Error creando'})
    except Exception as e:
        logging.error(f"❌ Error: {str(e)}")
        return jsonify({'success':False,'error':str(e)}),500

@app.route('/api/chequeo-general', methods=['POST'])
@login_required
def chequeo_general_puestos():
    try:
        user = session['user']
        if user['rol'] != 'IT_ADMIN':
            return jsonify({'success': False, 'error': 'No autorizado'}), 403
        data = request.get_json()
        resultados = data.get('resultados', [])
        incidencias_creadas = []
        for r in resultados:
            if r.get('estado') == 'malo':
                inc = mysql_db.crear_incidencia(
                    datos={'departamento': r.get('departamento'), 'puesto': r.get('puesto'), 'categoria': 'CHEQUEO_GENERAL',
                        'descripcion': f"Chequeo general: {r.get('descripcion', 'Problema detectado')}", 'prioridad': 'media'},
                    reportado_por_nombre=user['nombre_completo'], reportado_por_username=user['username'])
                if inc:
                    incidencias_creadas.append(inc['id'])
        return jsonify({'success': True, 'revisados': len(resultados), 'incidencias_creadas': len(incidencias_creadas)})
    except Exception as e:
        logging.error(f"❌ Error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/chequeo/guardar-lote', methods=['POST'])
@login_required
def guardar_chequeo_lote():
    """Guardar chequeo completo con detalle de componentes"""
    try:
        user = session['user']
        if user['rol'] != 'IT_ADMIN':
            return jsonify({'success': False, 'error': 'No autorizado'}), 403
        
        data = request.get_json()
        resultados = data.get('resultados', [])
        
        procesados = 0
        incidencias_creadas = 0
        chequeos_guardados = 0

        
        for r in resultados:
            dept = r.get('departamento')
            puesto = r.get('puesto')
            componentes = r.get('componentes', {})
            observaciones = r.get('observaciones', '')
            
            # Identificar componentes con problemas
            problemas = [k for k, v in componentes.items() if v == 'mal']
            
            if problemas:
                # Crear incidencia con descripción detallada
                descripcion = f"Chequeo general - Componentes con problemas: {', '.join(problemas)}"
                if observaciones:
                    descripcion += f". Observaciones: {observaciones}"
                
                inc = mysql_db.crear_incidencia(
                    datos={
                        'departamento': dept,
                        'puesto': f"{dept.upper()}-{puesto}",
                        'categoria': 'CHEQUEO_GENERAL',
                        'descripcion': descripcion,
                        'prioridad': 'media' if len(problemas) < 3 else 'alta'
                    },
                    reportado_por_nombre=user['nombre_completo'],
                    reportado_por_username=user['username']
                )
                if inc:
                    incidencias_creadas += 1
            
            # Guardar registro de chequeo SIEMPRE (independiente de si hay problemas)
            try:
                chequeo_id = mysql_db.guardar_chequeo_completo(
                    departamento=dept,
                    puesto=puesto,
                    componentes=componentes,
                    observaciones=observaciones,
                    usuario_id=user.get('id'),
                    usuario_nombre=user['nombre_completo']
                )
                if chequeo_id:
                    chequeos_guardados += 1
            except Exception as e:
                logging.warning(f"⚠️ No se pudo guardar detalle de chequeo: {e}")
            
            procesados += 1
        
        logging.info(f"📋 Chequeo lote completado por {user['username']}: {procesados} puestos, {chequeos_guardados} registros, {incidencias_creadas} incidencias")
        
        return jsonify({
            'success': True,
            'procesados': procesados,
            'chequeos_guardados': chequeos_guardados,
            'incidencias_creadas': incidencias_creadas
        })

        
    except Exception as e:
        logging.error(f"❌ Error en chequeo lote: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/zebra/config/sleep-timeout', methods=['POST'])
@login_required
def configurar_sleep_timeout():
    """Configurar timeout de suspensión de impresoras Zebra"""
    try:
        user = session['user']
        if user['rol'] != 'IT_ADMIN':
            return jsonify({'success': False, 'error': 'No autorizado'}), 403
        
        data = request.get_json()
        departamento = data.get('departamento', 'todos')
        timeout_minutos = int(data.get('timeout_minutos', 120))  # Default 2 horas
        desde = data.get('desde')
        hasta = data.get('hasta')
        
        # Comando SGD para configurar power timeout
        # timeout_minutos = 0 significa desactivar suspensión
        if timeout_minutos == 0:
            # Desactivar suspensión completamente
            zpl_cmd = '! U1 setvar "power.dpm.enable" "off"\r\n'
        else:
            # Activar suspensión con timeout específico
            zpl_cmd = f'! U1 setvar "power.dpm.enable" "on"\r\n! U1 setvar "power.dpm.timer.idle" "{timeout_minutos}"\r\n'
        
        departamentos = ['packing', 'return', 'vas'] if departamento == 'todos' else [departamento]
        
        actualizadas = 0
        fallidas = 0
        
        for dept in departamentos:
            if dept not in zebra_config:
                continue
            
            for puesto, config in zebra_config[dept].items():
                # Filtrar por rango si se especifica
                if desde and puesto < desde:
                    continue
                if hasta and puesto > hasta:
                    continue
                
                ip = config.get('ip')
                if not ip:
                    continue
                
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(5)
                    sock.connect((ip, 6101))
                    sock.sendall(zpl_cmd.encode('utf-8'))
                    sock.close()
                    actualizadas += 1
                    logging.info(f"⏰ Sleep timeout configurado: {dept.upper()}-{puesto} = {timeout_minutos} min")
                except Exception as e:
                    fallidas += 1
                    logging.warning(f"⚠️ Error configurando sleep en {dept}-{puesto}: {str(e)}")
        
        timeout_texto = "DESACTIVADA" if timeout_minutos == 0 else f"{timeout_minutos} minutos"
        logging.info(f"📊 Configuración sleep por {user['username']}: {actualizadas} OK, {fallidas} fallidas (timeout: {timeout_texto})")
        
        return jsonify({
            'success': True,
            'actualizadas': actualizadas,
            'fallidas': fallidas,
            'timeout_minutos': timeout_minutos
        })
        
    except Exception as e:
        logging.error(f"❌ Error configurando sleep timeout: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500



# =============================================================================
# WORKER DE CHEQUEO PERIÓDICO DE IMPRESORAS (CONTRASTE A 5)
# =============================================================================
import threading
import time as time_module

def worker_chequeo_impresoras():
    """
    Worker que verifica periódicamente las impresoras Zebra no bloqueadas
    y corrige el contraste a 5 si difiere del valor esperado.
    Se ejecuta cada 5 minutos.
    """
    logging.info("🔄 Worker de chequeo de impresoras iniciado")
    
    # Esperar 60 segundos antes de iniciar para que el servidor arranque
    time_module.sleep(60)
    
    while True:
        try:
            if not mysql_db:
                time_module.sleep(300)
                continue
            
            impresoras = mysql_db.get_todas_zebra(activas_solo=True)
            corregidas = 0
            verificadas = 0
            
            for imp in impresoras:
                try:
                    dept = imp['departamento']
                    puesto = imp['puesto']
                    
                    # Saltar impresoras bloqueadas
                    if imp.get('custom_locked'):
                        continue
                    
                    verificadas += 1
                    
                    # Obtener IP
                    if dept not in zebra_config or puesto not in zebra_config[dept]:
                        continue
                    
                    ip = zebra_config[dept][puesto]['ip']
                    
                    # Consultar contraste actual
                    try:
                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock.settimeout(3)
                        sock.connect((ip, 6101))
                        sock.sendall(b'! U1 getvar "print.tone"\r\n')
                        response = sock.recv(1024).decode().strip().replace('"', '')
                        sock.close()
                        
                        # Si el contraste no es 5, corregirlo
                        if response and response.isdigit() and int(response) != 5:
                            logging.info(f"⚠️ {dept.upper()}-{puesto}: contraste={response}, corrigiendo a 5")
                            
                            # Enviar corrección
                            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                            sock.settimeout(5)
                            sock.connect((ip, 6101))
                            sock.sendall(b'! U1 setvar "print.tone" "5"\r\n')
                            sock.close()
                            
                            # Actualizar en BD
                            mysql_db.actualizar_configuracion_zebra_parcial(dept, puesto, darkness_custom=5)
                            corregidas += 1
                            logging.info(f"✅ {dept.upper()}-{puesto}: contraste corregido a 5")
                            
                    except socket.timeout:
                        pass  # Impresora no responde, saltar
                    except Exception as e:
                        pass  # Error de conexión, saltar
                        
                except Exception as e:
                    pass
            
            if corregidas > 0:
                logging.info(f"📊 Chequeo periódico: {verificadas} verificadas, {corregidas} corregidas a contraste 5")
            
            # Esperar 5 minutos antes del siguiente chequeo
            time_module.sleep(300)
            
        except Exception as e:
            logging.error(f"❌ Error en worker de chequeo de impresoras: {str(e)}")
            time_module.sleep(300)

# Iniciar worker en thread separado
worker_thread = threading.Thread(target=worker_chequeo_impresoras, daemon=True)
worker_thread.start()


# =============================================================================
# FUNCIÓN PRINCIPAL - PUNTO DE ENTRADA
# =============================================================================
def main():
    """Función principal que inicia el servidor"""
    try:
        print("=" * 80)
        print("🚀 INICIANDO SERVIDOR - DASHBOARD DE CONTROL LOGISTICO v2.4")
        print("=" * 80)
        
        print("\n📂 Cargando configuraciones...")
        
        # 0️⃣ Opcional: Crear BD y poblarla si no existe para modo local
        try:
            from config import SQLiteConfig
            from pathlib import Path
            import os
            db_path = SQLiteConfig.get_config().get('database_path')
            if db_path and not Path(db_path).exists():
                print("   🛠️  Base de datos no encontrada. Generando datos iniciales locales...")
                import sys
                
                # Importar función seed_db desde poblar_local.py
                try:
                    # Añadir directorio raíz a sys.path temporalmente si es necesario
                    if getattr(sys, 'frozen', False):
                        root_dir = Path(sys.executable).parent
                    else:
                        root_dir = Path(__file__).resolve().parent.parent
                        
                    if str(root_dir) not in sys.path:
                        sys.path.insert(0, str(root_dir))
                        
                    import poblar_local
                    poblar_local.seed_db()
                    print("   ✅ Base de datos generada exitosamente.")
                except Exception as ex:
                    print(f"   ❌ Error al generar datos iniciales: {ex}")
        except Exception as e:
            pass

        # 1️⃣ PRIMERO: Conectar Base de Datos
        print("   1️⃣ Conectando a Base de Datos (MySQL/SQLite)...")
        connected = False
        try:
            connected = load_incidencias_from_db()
        except:
            connected = False

        if not connected:
            print("   ⚠️  Base de datos no disponible. ACTIVANDO MODO DEMO (Datos ficticios)")
            IS_DEMO_MODE = True
            # Inyectar datos de prueba para navegación local
            global usuarios_sistema, machines_config, rfid_config, zebra_config, tipos_incidencias, active_users_cache
            
            # Usuarios del sistema de prueba
            usuarios_sistema = {
                'admin': {
                    'id': 1,
                    'username': 'admin',
                    'password': 'admin123',
                    'rol': 'IT_ADMIN',
                    'departamento': 'IT',
                    'nombre_completo': 'Administrador de Pruebas',
                    'activo': 1
                },
                'supervisor': {
                    'id': 2,
                    'username': 'supervisor',
                    'password': 'super123',
                    'rol': 'SUPERVISOR',
                    'departamento': 'PACKING',
                    'nombre_completo': 'Juan García López',
                    'activo': 1
                },
                'tecnico': {
                    'id': 3,
                    'username': 'tecnico',
                    'password': 'tec123',
                    'rol': 'TECNICO',
                    'departamento': 'IT',
                    'nombre_completo': 'María Fernández Ruiz',
                    'activo': 1
                },
                'jefe': {
                    'id': 4,
                    'username': 'jefe',
                    'password': 'jefe123',
                    'rol': 'JEFE_EQUIPO',
                    'departamento': 'PACKING',
                    'nombre_completo': 'Andrés Jefe de Equipo',
                    'activo': 1
                }
            }

            
            # Tipos de incidencias
            tipos_incidencias = [
                {'id': 1, 'codigo': 'RFID_NO_LEE', 'nombre': 'RFID No Lee', 'prioridad_default': 'alta'},
                {'id': 2, 'codigo': 'ITEM_NOT_FOUND', 'nombre': 'Item No Encontrado', 'prioridad_default': 'media'},
                {'id': 3, 'codigo': 'IMPRESORA_ZEBRA', 'nombre': 'Problema Impresora', 'prioridad_default': 'media'},
                {'id': 4, 'codigo': 'PC_LENTO', 'nombre': 'Ordenador Lento', 'prioridad_default': 'baja'},
                {'id': 5, 'codigo': 'PANTALLA', 'nombre': 'Problema Pantalla', 'prioridad_default': 'media'},
                {'id': 6, 'codigo': 'OTRO', 'nombre': 'Otro Problema', 'prioridad_default': 'media'}
            ]
            
            # Puestos de prueba - PACKING (60 puestos)
            for i in range(1, 61):
                machines_config['packing'][i] = f'10.128.1.{i}'
                rfid_config['packing'][i] = f'10.128.2.{i}'
                zebra_config['packing'][i] = {'ip': f'10.128.3.{i}', 'puesto': i, 'left_position': 0, 'darkness_custom': 5}

            # Puestos de prueba - RETURN (20 puestos)
            for i in range(1, 21):
                machines_config['return'][i] = f'10.128.4.{i}'
                rfid_config['return'][i] = f'10.128.5.{i}'
                zebra_config['return'][i] = {'ip': f'10.128.6.{i}', 'puesto': i, 'left_position': -215, 'darkness_custom': 5}

            # Puestos de prueba - VAS (7 puestos)
            for i in range(1, 8):
                machines_config['vas'][i] = f'10.128.7.{i}'
                rfid_config['vas'][i] = f'10.128.8.{i}'
                zebra_config['vas'][i] = {'ip': f'10.128.9.{i}', 'puesto': i, 'left_position': -215, 'darkness_custom': 5}


            # Usuarios activos simulados (85% ocupados)
            import random
            nombres_masc = ["Carlos", "Pedro", "Luis", "Jose", "Miguel", "Andres", "Javier", "Fernando", "Ricardo", "Hugo"]
            nombres_fem = ["Ana", "Maria", "Carmen", "Laura", "Sofia", "Elena", "Lucia", "Isabel", "Marta", "Julia"]
            apellidos = ["Garcia", "Lopez", "Martinez", "Sanchez", "Perez", "Gomez", "Martin", "Jimenez", "Ruiz", "Hernandez"]
            
            def gen_nombre():
                n = random.choice(nombres_masc + nombres_fem)
                a = random.choice(apellidos)
                return f"{n} {a[0]}."

            active_users_cache = {}
            
            # Repartir operarios por departamento
            depts_puestos = [('packing', 60), ('return', 20), ('vas', 7)]
            total_ocupados = 0
            
            # Puestos que estarán apagados (offline) - sin usuario y fallarán ping
            # IPs que terminan en 0, 6, 12, 18, 24, 30, 36, 42, 48, 54, 60
            puestos_apagados = {
                'packing': [6, 12, 18, 24, 30, 36, 42, 48, 54, 60],  # ~17%
                'return': [6, 12, 18],  # ~15%
                'vas': [6]  # ~14%
            }
            
            for dept, max_puesto in depts_puestos:
                # Calcular cuántos puestos ocupar (~65-70%)
                # Excluir los que estarán apagados
                apagados = set(puestos_apagados.get(dept, []))
                disponibles = [p for p in range(1, max_puesto + 1) if p not in apagados]
                
                # Ocupar ~80% de los disponibles (lo que da ~65-70% del total)
                num_ocupados = int(len(disponibles) * 0.80)
                ocupados = random.sample(disponibles, num_ocupados)
                
                for p in ocupados:
                    nombre = gen_nombre()
                    prefix = {'packing': 'PACK', 'return': 'RET', 'vas': 'VAS'}[dept]
                    active_users_cache[f"{dept}-{p}"] = {
                        'station': f"{prefix}-{p}",
                        'usuario': f"USR{prefix}{p:03d}",
                        'nombre': nombre,
                        'hora': f"{random.randint(6,9):02d}:{random.randint(0,59):02d}"
                    }
                    total_ocupados += 1

            # Generar IPs de impresoras aleatorias
            for dept, max_puesto in depts_puestos:
                for i in range(1, max_puesto + 1):
                    # Solo IPs de impresoras para puestos aleatorios (pueden ser todos)
                    zebra_config[dept][i]['ip'] = f"192.168.10.{random.randint(10, 250)}"

            # Contar estados para verificación
            total_puestos = sum(max_p for _, max_p in depts_puestos)
            total_apagados = sum(len(puestos_apagados.get(dept, [])) for dept, _ in depts_puestos)
            total_libres = total_puestos - total_ocupados - total_apagados
            
            print("   ✅ Datos DEMO cargados correctamente:")
            print(f"      - Usuarios sistema: {len(usuarios_sistema)}")
            print(f"      - Puestos Packing: {len(machines_config['packing'])}")
            print(f"      - Puestos Return: {len(machines_config['return'])}")
            print(f"      - Puestos VAS: {len(machines_config['vas'])}")
            print(f"      - Operarios activos (Trabajando): {total_ocupados} (~{100*total_ocupados//total_puestos}%)")
            print(f"      - Puestos libres (Verde): {total_libres} (~{100*total_libres//total_puestos}%)")
            print(f"      - Puestos apagados (Gris): {total_apagados} (~{100*total_apagados//total_puestos}%)")

        else:
            # 2️⃣ SEGUNDO: Cargar usuarios desde MySQL real
            print("   2️⃣ Cargando usuarios...")
            load_users_from_mysql()
            
            # 3️⃣ Cargar tipos de incidencias
            print("   3️⃣ Cargando tipos de incidencias...")
            load_tipos_incidencias()
            
            # 4️⃣ Cargar configuración de puestos
            print("   4️⃣ Cargando configuración de puestos...")
            load_machines_from_mysql()
            load_rfid_from_mysql()
            load_zebra_from_mysql()

            # ✅ Rellenar caché de usuarios demo basado en los puestos cargados
            # (Oracle no está disponible, usamos datos simulados para mostrar el dashboard)
            print("   5️⃣ Generando usuarios demo para visualización...")
            nombres_masc = ["Carlos", "Pedro", "Luis", "Jose", "Miguel", "Andres", "Javier", "Fernando"]
            nombres_fem = ["Ana", "Maria", "Carmen", "Laura", "Sofia", "Elena", "Lucia", "Isabel"]
            apellidos = ["Garcia", "Lopez", "Martinez", "Sanchez", "Perez", "Gomez", "Martin", "Jimenez"]
            import random as _rand
            
            def _gen_nombre():
                n = _rand.choice(nombres_masc + nombres_fem)
                a = _rand.choice(apellidos)
                return f"{n} {a[0]}."

            puestos_apagados_bbdd = {
                'packing': {25, 50},
                'return': {25},
                'vas': set()
            }

            for dept, puestos in machines_config.items():
                apagados = puestos_apagados_bbdd.get(dept, set())
                prefix = {'packing': 'PACK', 'return': 'RET', 'vas': 'VAS'}.get(dept, dept.upper())
                disponibles = [p for p in puestos.keys() if p not in apagados]
                num_ocupados = int(len(disponibles) * 0.80)
                ocupados = _rand.sample(disponibles, min(num_ocupados, len(disponibles)))
                for p in ocupados:
                    active_users_cache[f"{dept}-{p}"] = {
                        'station': f"{prefix}-{p}",
                        'usuario': f"USR{prefix}{p:03d}",
                        'nombre': _gen_nombre(),
                        'hora': f"{_rand.randint(6,9):02d}:{_rand.randint(0,59):02d}"
                    }

            total_users = len(active_users_cache)
            print(f"   ✅ {total_users} operarios demo cargados en visualización")
        
        # Obtener IP local y puerto
        local_ip = get_local_ip()
        port = flask_config.get('port', 8503)
        
        print(f"\n🚀 SERVIDOR EN MODO PRUEBAS LOCALES")
        print(f"🌐 Ver programa aquí: http://localhost:{port}")
        print(f"👤 Login demo: admin / admin123")
        print("🛑 Presiona Ctrl+C para detener\n")
        print("=" * 80)

        
        # Verificar si SSL está habilitado
        try:
            from config import SSLConfig
            ssl_context = SSLConfig.get_ssl_context()
            if ssl_context:
                print("🔒 HTTPS habilitado")
                print(f"   • Certificado: {ssl_context[0]}")
                print(f"   • Clave: {ssl_context[1]}")
        except ImportError:
            ssl_context = None
        
        # Abrir el navegador en segundo plano (solo si no es .exe, el launcher ya lo abre)
        if not getattr(sys, 'frozen', False):
            import threading
            import webbrowser
            import time
            
            def open_browser():
                time.sleep(3)
                try:
                    protocol = "https" if ssl_context else "http"
                    webbrowser.open(f"{protocol}://localhost:{port}/")
                except Exception:
                    pass
                    
            threading.Thread(target=open_browser, daemon=True).start()

        # Iniciar servidor Flask
        if ssl_context:
            app.run(
                host='0.0.0.0',
                port=port,
                debug=False,
                threaded=True,
                ssl_context=ssl_context
            )
        else:
            app.run(
                host='0.0.0.0',
                port=port,
                debug=False,
                threaded=True
            )
        
    except KeyboardInterrupt:
        print("\n\n🛑 Servidor detenido por el usuario")
    except Exception as e:
        logging.error(f"❌ Error fatal: {str(e)}")
        import traceback
        traceback.print_exc()
        print("\nEl servidor ha fallado. Revisa el error anterior.")
        input("Presiona ENTER para cerrar...")
    finally:
        # Cerrar conexión MySQL al finalizar
        if mysql_db:
            mysql_db.close()
        # Cerrar conexión Oracle al finalizar
        if oracle_datos:
            oracle_datos.cerrar_conexion()
        print("\n👋 ¡Hasta pronto!")

if __name__ == '__main__':
    main()
