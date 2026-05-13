# Dashboard de Control Logístico

Sistema de monitorización en tiempo real para el control de estaciones de trabajo en entornos logísticos. Permite gestionar incidencias, visualizar el estado de los puestos por departamento y analizar métricas de rendimiento del equipo de soporte técnico.

Proyecto desarrollado como Trabajo de Fin de Grado del Ciclo Formativo de Grado Superior en Desarrollo de Aplicaciones Multiplataforma (DAM).

Autor: Jorge Carrasco López


## Qué hace este proyecto

- Monitoriza la conectividad de los puestos de trabajo haciendo ping automático a todas las IPs configuradas.
- Muestra en un tablero visual qué operario está trabajando en cada puesto, consultando los datos en tiempo real desde Oracle.
- Gestiona incidencias técnicas con un sistema de ticketing completo: crear, asignar, pausar, reanudar y resolver.
- Controla el acceso con tres roles de usuario: Administrador IT, Supervisor y Técnico, cada uno con permisos distintos.
- Ofrece un panel de analytics con gráficos interactivos para analizar distribución de incidencias, horas pico, rendimiento de técnicos y cumplimiento de SLA.
- Permite el reinicio remoto de lectores RFID por SSH y la conexión directa a puestos mediante TeamViewer.


## Tecnologías utilizadas

Backend:
- Python 3.13
- Flask 3.1.2
- PyMySQL 1.1.2 (conexión a MySQL)
- JayDeBeApi 1.2.3 + JPype1 1.6.0 (conexión a Oracle vía JDBC)
- Flask-Limiter 4.1.1, Flask-WTF 1.2.2, Flask-CORS 6.0.2 (seguridad)
- Paramiko (reinicio RFID por SSH)
- PyInstaller 6.12.0 (empaquetado como .exe)

Frontend:
- HTML5
- CSS3
- JavaScript ES6+ (sin frameworks)
- Chart.js 4.5.1 y Plotly.js 2.26.0 (gráficos)
- Font Awesome 6.0.0 (iconos)

Bases de datos:
- MySQL 8.0 — base de datos principal en producción
- SQLite 3 — alternativa local para pruebas (se activa automáticamente si MySQL no está disponible)
- Oracle Database — fuente de datos de operarios activos en tiempo real


## Estructura del proyecto

```
DASHBOARD - UNIVERSIDAD/
├── backend/
│   ├── ping_server.py          # Servidor Flask principal
│   ├── config.py               # Carga de configuración desde .env
│   ├── security.py             # Hash de contraseñas y tokens
│   ├── mysql_incidencias.py    # Módulo de conexión a MySQL
│   ├── sqlite_incidencias.py   # Módulo de conexión a SQLite
│   ├── analytics_endpoint.py   # Endpoint de analytics
│   ├── config_endpoints.py     # Endpoints de configuración
│   ├── modulo_db_oracle/       # Conexión a Oracle (JDBC)
│   ├── utils/                  # Validadores de entrada
│   └── .env                    # Credenciales (no incluido en el repo)
├── frontend/
│   ├── tablero.html            # Página principal del dashboard
│   ├── login.html              # Página de inicio de sesión
│   ├── analytics.js            # Lógica del panel de analytics
│   ├── config_functions.js     # Lógica de configuración de hardware
│   ├── libs/                   # Chart.js, Plotly.js, Font Awesome
│   └── assets/                 # Imágenes e iconos
├── database/
│   ├── setup_database.sql      # Esquema de tablas MySQL
│   └── demo_data.sql           # Datos de prueba
├── config/
│   ├── mesas.csv               # Configuración de puestos
│   └── puestos_rfid.csv        # Configuración de dispositivos RFID
├── build_exe.spec              # Configuración de PyInstaller
├── requirements.txt            # Dependencias Python
└── README.md
```


## Instalación y puesta en marcha

Requisitos previos:
- Python 3.10 o superior
- Servidor MySQL (opcional, el sistema funciona también con SQLite)
- Navegador web moderno

Pasos:

1. Instalar las dependencias de Python:

```
pip install -r requirements.txt
```

2. (Opcional) Si vas a usar MySQL, importar el esquema y los datos de prueba:

```
mysql -u root -p < database/setup_database.sql
mysql -u root -p < database/demo_data.sql
```

3. Configurar el fichero de credenciales. Copia el archivo `backend/.env.example` a `backend/.env` y rellena tus datos de conexión (MySQL, Oracle, contraseña SSH, etc.).

4. Arrancar el servidor:

```
python backend/ping_server.py
```

5. Abrir `http://localhost:5000` en el navegador. El sistema abrirá el navegador automáticamente.

Si no hay ninguna base de datos configurada, el sistema arranca en modo demo con datos simulados.


## Credenciales de prueba

| Usuario    | Contraseña | Rol               |
|------------|------------|--------------------|
| admin      | admin123   | Administrador IT   |
| supervisor | super123   | Supervisor         |
| tecnico    | tec123     | Técnico            |


## Ejecutable (.exe)

El proyecto puede empaquetarse como ejecutable para Windows sin necesidad de instalar Python:

```
pyinstaller build_exe.spec
```

El ejecutable generado incluye el backend, el frontend y el driver de Oracle en un solo fichero.
