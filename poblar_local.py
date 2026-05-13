"""
=============================================================================
SCRIPT DE SEMILLA PARA SQLITE - Dashboard de Control
=============================================================================
Este script puebla la base de datos SQLite local con datos iniciales
para que se pueda ver el programa en funcionamiento inmediatamente.
=============================================================================
"""

import sqlite3
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
import random

# Añadir el backend al path para poder importar config
current_dir = Path(__file__).resolve().parent
backend_dir = current_dir / 'backend'
sys.path.append(str(backend_dir))

try:
    # Intentar obtenerla del config
    from config import SQLiteConfig
    db_path = SQLiteConfig.get_config()['database_path']
except Exception:
    # Fallback manual robusto
    db_path = current_dir / 'backend' / 'database' / 'incidencias.db'
    if not db_path.parent.exists():
        db_path = current_dir / 'database' / 'incidencias.db'

def seed_db():
    print(f"🚀 Iniciando población de base de datos: {db_path}")
    
    if not os.path.exists(os.path.dirname(db_path)):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 1. Limpiar datos existentes
        print("🧹 Limpiando datos previos...")
        cursor.execute("DELETE FROM comentarios_incidencias")
        cursor.execute("DELETE FROM historial_incidencias")
        cursor.execute("DELETE FROM incidencias")
        cursor.execute("DELETE FROM usuarios")
        cursor.execute("DELETE FROM mesas")
        cursor.execute("DELETE FROM rfid")
        cursor.execute("DELETE FROM impresoras_zebra")
        
        # 2. Usuarios
        print("👤 Insertando usuarios...")
        usuarios = [
            ('admin', 'admin123', 'Administrador de IT', 'IT_ADMIN', 'IT'),
            ('supervisor', 'super123', 'Supervisor de Turno', 'SUPERVISOR', 'OPERACIONES'),
            ('tecnico', 'tec123', 'Técnico de Soporte', 'TECNICO', 'IT'),
            ('jefe_packing', 'jefe123', 'Jefe de Equipo Packing', 'JEFE_EQUIPO', 'PACKING')
        ]
        cursor.executemany(
            "INSERT INTO usuarios (username, password, nombre_completo, rol, departamento) VALUES (?, ?, ?, ?, ?)",
            usuarios
        )
        
        # 3. Mesas (Configuración del sistema)
        print("🖥️ Insertando configuración de mesas...")
        mesas = []
        # Packing: 1 a 60
        for i in range(1, 61):
            mesas.append(('packing', i, f'10.128.1.{i}'))
        # Return: 1 a 20
        for i in range(1, 21):
            mesas.append(('return', i, f'10.128.4.{i}'))
        # VAS: 1 a 7
        for i in range(1, 8):
            mesas.append(('vas', i, f'10.128.7.{i}'))
            
        cursor.executemany("INSERT INTO mesas (departamento, puesto, ip) VALUES (?, ?, ?)", mesas)
        
        # 4. RFID e Impresoras
        print("🏷️ Insertando dispositivos RFID e impresoras...")
        rfids = []
        zebras = []
        for i in range(1, 11):
            rfids.append(('packing', i, f'10.128.2.{i}', f'RFID-PACK-{i}'))
            zebras.append(('packing', i, f'192.168.10.{100+i}', 9100, 'ZD421'))
            
        cursor.executemany("INSERT INTO rfid (departamento, puesto, ip, nombre_dispositivo) VALUES (?, ?, ?, ?)", rfids)
        cursor.executemany("INSERT INTO impresoras_zebra (departamento, puesto, ip, puerto, modelo) VALUES (?, ?, ?, ?, ?)", zebras)
        
        # 5. Incidencias
        print("⚠️ Generando incidencias de prueba...")
        categorias = ['PC_NO_ENCIENDE', 'PC_LENTO', 'SIN_INTERNET', 'IMPRESORA', 'RFID_ERROR', 'OTRO']
        depts = ['packing', 'return', 'vas']
        nombres = ['Marcos G.', 'Lucia H.', 'Roberto L.', 'Elena S.', 'Victor M.']
        
        # 50 incidencias históricas
        for i in range(50):
            dept = random.choice(depts)
            puesto = random.randint(1, 10)
            categoria = random.choice(categorias)
            prioridad = random.choice(['BAJA', 'MEDIA', 'ALTA', 'CRÍTICA'])
            estado = random.choice(['pendiente', 'en_proceso', 'resuelta'])
            reportado_por = random.choice(nombres)
            
            # Fecha aleatoria en los últimos 7 días
            dias_atras = random.randint(0, 7)
            fecha = datetime.now() - timedelta(days=dias_atras, hours=random.randint(0, 23))
            fecha_str = fecha.strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute("""
                INSERT INTO incidencias 
                (departamento, puesto, categoria, descripcion, prioridad, estado, reportado_por, reportado_por_username, fecha_creacion)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (dept, puesto, categoria, f"Problema simulado de {categoria}", prioridad, estado, reportado_por, reportado_por.lower().replace(' ', '.'), fecha_str))
            
            inc_id = cursor.lastrowid
            
            import json
            
            # Evento 1: Creación (PENDIENTE)
            cursor.execute("""
                INSERT INTO historial_incidencias (incidencia_id, tipo_evento, descripcion, usuario, username, datos_adicionales, fecha_evento)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (inc_id, 'CREADA', 'Incidencia reportada', reportado_por, reportado_por.lower().replace(' ', '.'), json.dumps({'nuevo': 'pendiente'}), fecha_str))
            
            if estado in ['en_proceso', 'resuelta']:
                # Evento 2: EN PROGRESO
                fecha_progreso = fecha + timedelta(minutes=random.randint(5, 30))
                cursor.execute("""
                    INSERT INTO historial_incidencias (incidencia_id, tipo_evento, descripcion, usuario, username, datos_adicionales, fecha_evento)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (inc_id, 'EN_PROCESO', 'Estado cambiado a en_proceso', 'Técnico IT', 'tecnico', json.dumps({'anterior': 'pendiente', 'nuevo': 'en_proceso'}), fecha_progreso.strftime('%Y-%m-%d %H:%M:%S')))
                
            if estado == 'resuelta':
                # Evento 3: RESUELTA
                fecha_res = fecha + timedelta(hours=random.randint(1, 5))
                cursor.execute("""
                    UPDATE incidencias SET fecha_resolucion = ?, resuelto_por = ?, notas_resolucion = ? WHERE id = ?
                """, (fecha_res.strftime('%Y-%m-%d %H:%M:%S'), 'Técnico IT', 'Problema resuelto correctamente.', inc_id))
                
                cursor.execute("""
                    INSERT INTO historial_incidencias (incidencia_id, tipo_evento, descripcion, usuario, username, datos_adicionales, fecha_evento)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (inc_id, 'RESUELTA', 'Estado cambiado a resuelta - Problema resuelto correctamente.', 'Técnico IT', 'tecnico', json.dumps({'anterior': 'en_proceso', 'nuevo': 'resuelta'}), fecha_res.strftime('%Y-%m-%d %H:%M:%S')))
        
        conn.commit()
        print("✅ Base de datos SQLite poblada exitosamente con historial de eventos.")
        
    except Exception as e:
        print(f"❌ Error poblando base de datos: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    seed_db()
