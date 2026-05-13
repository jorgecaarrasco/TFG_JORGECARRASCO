USE incidencias_dashboard;

-- Tabla para historial de chequeos generales
CREATE TABLE IF NOT EXISTS chequeos_generales (
    id INT AUTO_INCREMENT PRIMARY KEY,
    departamento VARCHAR(50) NOT NULL,
    puesto VARCHAR(20) NOT NULL,
    usuario_id INT,
    usuario_nombre VARCHAR(100),
    fecha_inicio DATETIME NOT NULL,
    fecha_fin DATETIME,
    estado ENUM('en_progreso', 'completado', 'pausado') DEFAULT 'en_progreso',
    
    -- Componentes chequeados
    pantalla ENUM('bueno', 'malo', 'pendiente') DEFAULT 'pendiente',
    ordenador ENUM('bueno', 'malo', 'pendiente') DEFAULT 'pendiente',
    teclado_cherry ENUM('bueno', 'malo', 'pendiente') DEFAULT 'pendiente',
    pistola ENUM('bueno', 'malo', 'pendiente') DEFAULT 'pendiente',
    impresora ENUM('bueno', 'malo', 'pendiente') DEFAULT 'pendiente',
    raton ENUM('bueno', 'malo', 'pendiente') DEFAULT 'pendiente',
    cognex ENUM('bueno', 'malo', 'pendiente') DEFAULT 'pendiente',
    rfid ENUM('bueno', 'malo', 'pendiente') DEFAULT 'pendiente',
    
    -- Observaciones
    observaciones TEXT,
    
    INDEX idx_departamento (departamento),
    INDEX idx_estado (estado),
    INDEX idx_fecha (fecha_inicio)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tabla para guardar progreso de chequeo en curso (para pausar/reanudar)
CREATE TABLE IF NOT EXISTS chequeos_progreso (
    id INT AUTO_INCREMENT PRIMARY KEY,
    chequeo_id INT,
    session_id VARCHAR(100) UNIQUE,
    usuario_id INT,
    departamento VARCHAR(50),
    rango_desde INT,
    rango_hasta INT,
    filtro VARCHAR(20),
    puestos_completados TEXT, -- JSON array de puestos ya chequeados
    ultimo_puesto VARCHAR(20),
    fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (chequeo_id) REFERENCES chequeos_generales(id) ON DELETE CASCADE,
    INDEX idx_session (session_id),
    INDEX idx_usuario (usuario_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
