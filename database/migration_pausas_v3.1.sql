-- =====================================================================
-- SCRIPT DE MIGRACIÓN - SISTEMA DE PAUSAS PARA INCIDENCIAS
-- Base de datos: incidencias_dashboard
-- Versión: 3.1
-- Fecha: 2024-12-23
-- =====================================================================

USE incidencias_dashboard;

-- =====================================================================
-- 1. MODIFICAR TABLA incidencias - Añadir estado 'pausada'
-- =====================================================================

-- Cambiar el ENUM de estado para incluir 'pausada'
ALTER TABLE incidencias 
MODIFY COLUMN estado ENUM('pendiente', 'en_proceso', 'pausada', 'resuelta') DEFAULT 'pendiente';

-- Añadir campos para control de pausas
ALTER TABLE incidencias 
ADD COLUMN IF NOT EXISTS tiempo_pausado_minutos INT DEFAULT 0 
COMMENT 'Tiempo total que la incidencia ha estado pausada (en minutos)';

ALTER TABLE incidencias 
ADD COLUMN IF NOT EXISTS motivo_pausa_actual VARCHAR(100) NULL 
COMMENT 'Motivo de la pausa actual (NULL si no está pausada)';

ALTER TABLE incidencias 
ADD COLUMN IF NOT EXISTS fecha_ultima_pausa DATETIME NULL 
COMMENT 'Fecha/hora de la última pausa';

-- =====================================================================
-- 2. CREAR TABLA motivos_pausa - Catálogo de motivos de pausa
-- =====================================================================

CREATE TABLE IF NOT EXISTS motivos_pausa (
    id INT AUTO_INCREMENT PRIMARY KEY,
    codigo VARCHAR(50) NOT NULL UNIQUE,
    descripcion VARCHAR(100) NOT NULL,
    requiere_descripcion BOOLEAN DEFAULT FALSE COMMENT 'Si requiere descripción adicional',
    activo BOOLEAN DEFAULT TRUE,
    orden INT DEFAULT 0 COMMENT 'Orden de aparición en la UI',
    fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP,
    fecha_modificacion DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    INDEX idx_activo (activo),
    INDEX idx_orden (orden)
    
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Catálogo de motivos de pausa para incidencias';

-- Insertar motivos de pausa iniciales
INSERT INTO motivos_pausa (codigo, descripcion, requiere_descripcion, orden) VALUES
('ESPERANDO_JEFE', 'Esperando Jefe de Equipo', FALSE, 1),
('ESPERANDO_SUPERVISOR', 'Esperando Supervisor', FALSE, 2),
('ESPERANDO_SERVICIO_TECNICO', 'Esperando Servicio Técnico Oficial', FALSE, 3),
('ESPERANDO_PROVEEDOR', 'Esperando Proveedor Externo', FALSE, 4),
('ESPERANDO_REPUESTO', 'Esperando Repuesto/Material', FALSE, 5),
('ESPERANDO_AUTORIZACION', 'Esperando Autorización', FALSE, 6),
('OTRO', 'Otro motivo', TRUE, 99)
ON DUPLICATE KEY UPDATE descripcion = VALUES(descripcion);

-- =====================================================================
-- 3. CREAR TABLA historial_pausas - Registro de todas las pausas
-- =====================================================================

CREATE TABLE IF NOT EXISTS historial_pausas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    incidencia_id INT NOT NULL,
    
    -- Información de la pausa
    motivo_codigo VARCHAR(50) NOT NULL COMMENT 'Código del motivo de pausa',
    motivo_descripcion VARCHAR(100) NOT NULL COMMENT 'Descripción del motivo (snapshot)',
    descripcion_adicional TEXT NULL COMMENT 'Descripción adicional proporcionada por el usuario',
    
    -- Quién pausó
    pausado_por VARCHAR(100) NOT NULL COMMENT 'Nombre completo del usuario que pausó',
    pausado_por_username VARCHAR(50) NOT NULL COMMENT 'Username del usuario que pausó',
    
    -- Fechas
    fecha_inicio_pausa DATETIME NOT NULL COMMENT 'Cuándo se pausó',
    fecha_fin_pausa DATETIME NULL COMMENT 'Cuándo se reanudó (NULL = aún pausada)',
    
    -- Duración calculada
    duracion_minutos INT DEFAULT 0 COMMENT 'Duración de la pausa en minutos',
    
    -- Información de reanudación (opcional)
    reanudado_por VARCHAR(100) NULL,
    reanudado_por_username VARCHAR(50) NULL,
    notas_reanudacion TEXT NULL COMMENT 'Notas al reanudar',
    
    -- Claves foráneas e índices
    FOREIGN KEY (incidencia_id) REFERENCES incidencias(id) ON DELETE CASCADE,
    INDEX idx_incidencia (incidencia_id),
    INDEX idx_fecha_inicio (fecha_inicio_pausa),
    INDEX idx_activa (fecha_fin_pausa)
    
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Historial de pausas de incidencias para tracking de tiempos';

-- =====================================================================
-- 4. CREAR TABLA historial_incidencias - Timeline completo
-- =====================================================================

CREATE TABLE IF NOT EXISTS historial_incidencias (
    id INT AUTO_INCREMENT PRIMARY KEY,
    incidencia_id INT NOT NULL,
    
    -- Tipo de evento
    tipo_evento ENUM(
        'CREADA',
        'EN_PROCESO', 
        'PAUSADA',
        'REANUDADA',
        'RESUELTA',
        'COMENTARIO',
        'EDITADA'
    ) NOT NULL,
    
    -- Información del evento
    descripcion TEXT NOT NULL COMMENT 'Descripción del evento',
    datos_adicionales JSON NULL COMMENT 'Datos adicionales en formato JSON',
    
    -- Quién realizó la acción
    usuario VARCHAR(100) NOT NULL,
    username VARCHAR(50) NOT NULL,
    
    -- Fecha
    fecha_evento DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    -- Claves foráneas e índices
    FOREIGN KEY (incidencia_id) REFERENCES incidencias(id) ON DELETE CASCADE,
    INDEX idx_incidencia (incidencia_id),
    INDEX idx_tipo (tipo_evento),
    INDEX idx_fecha (fecha_evento)
    
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Timeline completo de eventos de cada incidencia';

-- =====================================================================
-- 5. ACTUALIZAR VISTA incidencias_completas
-- =====================================================================

CREATE OR REPLACE VIEW incidencias_completas AS
SELECT 
    i.*,
    COUNT(DISTINCT c.id) as total_comentarios,
    COUNT(DISTINCT hp.id) as total_pausas,
    COALESCE(SUM(hp.duracion_minutos), 0) as tiempo_total_pausado,
    TIMESTAMPDIFF(MINUTE, i.fecha_creacion, COALESCE(i.fecha_resolucion, NOW())) as minutos_transcurridos,
    TIMESTAMPDIFF(MINUTE, i.fecha_creacion, COALESCE(i.fecha_resolucion, NOW())) - COALESCE(i.tiempo_pausado_minutos, 0) as minutos_efectivos
FROM incidencias i
LEFT JOIN comentarios_incidencias c ON i.id = c.incidencia_id
LEFT JOIN historial_pausas hp ON i.id = hp.incidencia_id AND hp.fecha_fin_pausa IS NOT NULL
GROUP BY i.id;

-- =====================================================================
-- 6. TRIGGER: Registrar en historial cuando se crea incidencia
-- =====================================================================

DELIMITER //

-- Eliminar trigger si existe
DROP TRIGGER IF EXISTS after_incidencia_insert//

CREATE TRIGGER after_incidencia_insert
AFTER INSERT ON incidencias
FOR EACH ROW
BEGIN
    INSERT INTO historial_incidencias (
        incidencia_id, 
        tipo_evento, 
        descripcion, 
        usuario, 
        username,
        datos_adicionales
    ) VALUES (
        NEW.id,
        'CREADA',
        CONCAT('Incidencia creada: ', NEW.categoria),
        NEW.reportado_por,
        NEW.reportado_por_username,
        JSON_OBJECT(
            'departamento', NEW.departamento,
            'puesto', NEW.puesto,
            'categoria', NEW.categoria,
            'prioridad', NEW.prioridad
        )
    );
END//

DELIMITER ;

-- =====================================================================
-- 7. PROCEDIMIENTO: Calcular métricas con pausas
-- =====================================================================

DELIMITER //

DROP PROCEDURE IF EXISTS obtener_estadisticas_generales//

CREATE PROCEDURE obtener_estadisticas_generales()
BEGIN
    SELECT 
        COUNT(*) as total_incidencias,
        SUM(CASE WHEN estado = 'pendiente' THEN 1 ELSE 0 END) as pendientes,
        SUM(CASE WHEN estado = 'en_proceso' THEN 1 ELSE 0 END) as en_proceso,
        SUM(CASE WHEN estado = 'pausada' THEN 1 ELSE 0 END) as pausadas,
        SUM(CASE WHEN estado = 'resuelta' THEN 1 ELSE 0 END) as resueltas,
        -- Tiempo promedio EFECTIVO (descontando pausas)
        AVG(CASE 
            WHEN estado = 'resuelta' 
            THEN TIMESTAMPDIFF(MINUTE, fecha_creacion, fecha_resolucion) - COALESCE(tiempo_pausado_minutos, 0)
            ELSE NULL 
        END) as promedio_minutos_efectivos,
        -- Tiempo promedio TOTAL
        AVG(CASE 
            WHEN estado = 'resuelta' 
            THEN TIMESTAMPDIFF(MINUTE, fecha_creacion, fecha_resolucion)
            ELSE NULL 
        END) as promedio_minutos_total,
        MIN(fecha_creacion) as fecha_primera_incidencia,
        MAX(fecha_creacion) as fecha_ultima_incidencia
    FROM incidencias;
END//

DELIMITER ;

-- =====================================================================
-- VERIFICACIÓN
-- =====================================================================

SELECT 'Migración completada exitosamente' as mensaje, NOW() as fecha;

-- Mostrar tablas nuevas
SELECT TABLE_NAME as 'Tablas del sistema' 
FROM information_schema.TABLES 
WHERE TABLE_SCHEMA = 'incidencias_dashboard'
ORDER BY TABLE_NAME;

-- Mostrar motivos de pausa
SELECT codigo, descripcion, orden FROM motivos_pausa WHERE activo = TRUE ORDER BY orden;

-- =====================================================================
-- FIN DE LA MIGRACIÓN
-- =====================================================================
