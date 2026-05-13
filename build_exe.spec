# -*- mode: python ; coding: utf-8 -*-
# =============================================================================
# Dashboard de Control Logistico - Configuracion PyInstaller
# =============================================================================

import os

block_cipher = None

# Rutas base
BASE_DIR = os.path.abspath('.')
BACKEND_DIR = os.path.join(BASE_DIR, 'backend')
FRONTEND_DIR = os.path.join(BASE_DIR, 'frontend')

a = Analysis(
    [os.path.join(BACKEND_DIR, 'ping_server.py')],
    pathex=[BACKEND_DIR],
    binaries=[],
    datas=[
        # Frontend completo
        (FRONTEND_DIR, 'frontend'),
        # Base de datos SQLite
        (os.path.join(BACKEND_DIR, 'database'), 'database'),
        # Configuración
        (os.path.join(BACKEND_DIR, '.env'), '.'),
        # Módulo Oracle
        (os.path.join(BACKEND_DIR, 'modulo_db_oracle'), 'modulo_db_oracle'),
        # Archivos jar de Oracle
        (os.path.join(BACKEND_DIR, 'ojdbc8.jar'), '.'),
        # Módulos Python locales
        (os.path.join(BACKEND_DIR, 'sqlite_incidencias.py'), '.'),
        (os.path.join(BACKEND_DIR, 'mysql_incidencias.py'), '.'),
        (os.path.join(BACKEND_DIR, 'config.py'), '.'),
        (os.path.join(BACKEND_DIR, 'security.py'), '.'),
        (os.path.join(BASE_DIR, 'poblar_local.py'), '.'),
    ],
    hiddenimports=[
        'flask',
        'flask_cors',
        'flask_limiter',
        'flask_limiter.util',
        'flask_wtf',
        'flask_wtf.csrf',
        'wtforms',
        'sqlite3',
        'json',
        'csv',
        'pathlib',
        'threading',
        'socket',
        'subprocess',
        'concurrent.futures',
        'logging',
        'random',
        'datetime',
        'hashlib',
        'secrets',
        'time',
        'os',
        'wakepy',
        'wakepy.keep',
        'dotenv',
        'pymysql',
        'modulo_db_oracle',
        'modulo_db_oracle.crud',
        'modulo_db_oracle.queries',
        'mysql_incidencias',
        'sqlite_incidencias',
        'config',
        'security',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'PIL',
        'cv2',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Dashboard_Control_Logistico',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    console=False,  # Ocultar consola para que sirva como ejecutable de fondo silencioso
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(FRONTEND_DIR, 'assets', 'jc.ico'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Dashboard_Control_Logistico',
)
