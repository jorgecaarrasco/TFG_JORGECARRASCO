-- =====================================================================
-- SCRIPT DE CREACIÓN DE BASE DE DATOS - INCIDENCIAS DASHBOARD
-- Base de datos: incidencias_dashboard
-- Versión: 1.0
-- =====================================================================

-- Usar la base de datos
USE incidencias_dashboard;

-- =====================================================================
-- TABLA: incidencias
-- Almacena todas las incidencias reportadas en el sistema
-- =====================================================================
CREATE TABLE IF NOT EXISTS incidencias (
    -- Identificador único
    id INT AUTO_INCREMENT PRIMARY KEY,
    
    -- Información del puesto
    departamento VARCHAR(50) NOT NULL COMMENT 'packing, return, vas',
    puesto INT NOT NULL COMMENT 'Número del puesto (ej: 12 para PACK-12)',
    
    -- Información de la incidencia
    categoria VARCHAR(100) NOT NULL COMMENT 'Tipo de incidencia',
    descripcion TEXT COMMENT 'Descripción detallada del problema',
    prioridad ENUM('BAJA', 'MEDIA', 'ALTA', 'CRÍTICA') DEFAULT 'MEDIA',
    
    -- Estado de la incidencia
    estado ENUM('pendiente', 'en_proceso', 'resuelta') DEFAULT 'pendiente',
    
    -- Información de seguimiento
    reportado_por VARCHAR(100) NOT NULL COMMENT 'Nombre completo del usuario',
    reportado_por_username VARCHAR(50) NOT NULL COMMENT 'Username del usuario',
    resuelto_por VARCHAR(100) DEFAULT NULL COMMENT 'Usuario que resolvió',
    
    -- Fechas
    fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP,
    fecha_actualizacion DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    fecha_resolucion DATETIME DEFAULT NULL,
    
    -- Notas adicionales
    notas_resolucion TEXT COMMENT 'Notas al resolver la incidencia',
    
    -- Índices para búsquedas rápidas
    INDEX idx_departamento (departamento),
    INDEX idx_puesto (puesto),
    INDEX idx_estado (estado),
    INDEX idx_fecha_creacion (fecha_creacion),
    INDEX idx_reportado_por_username (reportado_por_username),
    INDEX idx_dept_puesto (departamento, puesto)
    
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Registro de incidencias del sistema de control de mesas';

-- =====================================================================
-- TABLA: comentarios_incidencias
-- Almacena comentarios adicionales sobre las incidencias
-- =====================================================================
CREATE TABLE IF NOT EXISTS comentarios_incidencias (
    id INT AUTO_INCREMENT PRIMARY KEY,
    incidencia_id INT NOT NULL,
    usuario VARCHAR(100) NOT NULL,
    username VARCHAR(50) NOT NULL,
    comentario TEXT NOT NULL,
    fecha_comentario DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    -- Clave foránea
    FOREIGN KEY (incidencia_id) REFERENCES incidencias(id) ON DELETE CASCADE,
    
    -- Índices
    INDEX idx_incidencia (incidencia_id),
    INDEX idx_fecha (fecha_comentario)
    
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Comentarios adicionales sobre incidencias';

-- =====================================================================
-- TABLA: tipos_incidencias
-- Catálogo de tipos de incidencias disponibles
-- =====================================================================
CREATE TABLE IF NOT EXISTS tipos_incidencias (
    id INT AUTO_INCREMENT PRIMARY KEY,
    codigo VARCHAR(50) NOT NULL UNIQUE,
    descripcion VARCHAR(200) NOT NULL,
    categoria VARCHAR(100) NOT NULL,
    prioridad ENUM('BAJA', 'MEDIA', 'ALTA', 'CRÍTICA') DEFAULT 'MEDIA',
    activo BOOLEAN DEFAULT TRUE,
    fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    -- Índices
    INDEX idx_codigo (codigo),
    INDEX idx_activo (activo)
    
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Catálogo de tipos de incidencias';

-- =====================================================================
-- INSERTAR TIPOS DE INCIDENCIAS INICIALES
-- =====================================================================
INSERT INTO tipos_incidencias (codigo, descripcion, categoria, prioridad) VALUES
('PC_NO_ENCIENDE', 'PC no enciende', 'Hardware', 'ALTA'),
('PC_LENTO', 'PC muy lento', 'Rendimiento', 'MEDIA'),
('SIN_INTERNET', 'Sin conexión a Internet', 'Red', 'ALTA'),
('ERROR_SOFTWARE', 'Error en software/aplicación', 'Software', 'MEDIA'),
('TECLADO_RATON', 'Problema con teclado/ratón', 'Periféricos', 'MEDIA'),
('MONITOR', 'Problema con monitor/pantalla', 'Hardware', 'ALTA'),
('IMPRESORA', 'Problema con impresora', 'Periféricos', 'MEDIA'),
('RFID_ERROR', 'Error en lector RFID', 'Hardware', 'ALTA'),
('SIN_ACCESO', 'Sin acceso a sistema', 'Accesos', 'CRÍTICA'),
('OTRO', 'Otro problema', 'General', 'BAJA');

-- =====================================================================
-- VISTA: incidencias_completas
-- Vista con información completa de incidencias
-- =====================================================================
CREATE OR REPLACE VIEW incidencias_completas AS
SELECT 
    i.*,
    COUNT(c.id) as total_comentarios,
    TIMESTAMPDIFF(HOUR, i.fecha_creacion, COALESCE(i.fecha_resolucion, NOW())) as horas_transcurridas
FROM incidencias i
LEFT JOIN comentarios_incidencias c ON i.id = c.incidencia_id
GROUP BY i.id;

-- =====================================================================
-- VISTA: estadisticas_departamentos
-- Estadísticas por departamento
-- =====================================================================
CREATE OR REPLACE VIEW estadisticas_departamentos AS
SELECT 
    departamento,
    COUNT(*) as total_incidencias,
    SUM(CASE WHEN estado = 'pendiente' THEN 1 ELSE 0 END) as pendientes,
    SUM(CASE WHEN estado = 'en_proceso' THEN 1 ELSE 0 END) as en_proceso,
    SUM(CASE WHEN estado = 'resuelta' THEN 1 ELSE 0 END) as resueltas,
    AVG(TIMESTAMPDIFF(HOUR, fecha_creacion, fecha_resolucion)) as promedio_horas_resolucion
FROM incidencias
GROUP BY departamento;

-- =====================================================================
-- VISTA: top_puestos_problematicos
-- Top 20 puestos con más incidencias
-- =====================================================================
CREATE OR REPLACE VIEW top_puestos_problematicos AS
SELECT 
    departamento,
    puesto,
    CONCAT(UPPER(departamento), '-', puesto) as puesto_completo,
    COUNT(*) as total_incidencias,
    SUM(CASE WHEN estado = 'resuelta' THEN 1 ELSE 0 END) as resueltas,
    SUM(CASE WHEN estado IN ('pendiente', 'en_proceso') THEN 1 ELSE 0 END) as activas
FROM incidencias
GROUP BY departamento, puesto
ORDER BY total_incidencias DESC
LIMIT 20;

-- =====================================================================
-- PROCEDIMIENTO: obtener_estadisticas_generales
-- Obtiene estadísticas generales del sistema
-- =====================================================================
DELIMITER //
CREATE PROCEDURE obtener_estadisticas_generales()
BEGIN
    SELECT 
        COUNT(*) as total_incidencias,
        SUM(CASE WHEN estado = 'pendiente' THEN 1 ELSE 0 END) as pendientes,
        SUM(CASE WHEN estado = 'en_proceso' THEN 1 ELSE 0 END) as en_proceso,
        SUM(CASE WHEN estado = 'resuelta' THEN 1 ELSE 0 END) as resueltas,
        AVG(CASE 
            WHEN estado = 'resuelta' 
            THEN TIMESTAMPDIFF(HOUR, fecha_creacion, fecha_resolucion) 
            ELSE NULL 
        END) as promedio_horas_resolucion,
        MIN(fecha_creacion) as fecha_primera_incidencia,
        MAX(fecha_creacion) as fecha_ultima_incidencia
    FROM incidencias;
END //
DELIMITER ;

-- =====================================================================
-- TRIGGER: actualizar_fecha_resolucion
-- Actualiza automáticamente la fecha de resolución
-- =====================================================================
DELIMITER //
CREATE TRIGGER actualizar_fecha_resolucion
BEFORE UPDATE ON incidencias
FOR EACH ROW
BEGIN
    IF NEW.estado = 'resuelta' AND OLD.estado != 'resuelta' THEN
        SET NEW.fecha_resolucion = NOW();
    END IF;
END //
DELIMITER ;

-- =====================================================================
-- INFORMACIÓN DEL SISTEMA
-- =====================================================================
SELECT 
    'Base de datos creada exitosamente' as mensaje,
    DATABASE() as base_datos,
    NOW() as fecha_creacion;

SELECT 
    TABLE_NAME as tabla,
    TABLE_ROWS as filas_estimadas,
    ROUND(((DATA_LENGTH + INDEX_LENGTH) / 1024 / 1024), 2) as tamaño_mb
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = 'incidencias_dashboard'
ORDER BY TABLE_NAME;

-- =====================================================================
-- FIN DEL SCRIPT
-- =====================================================================