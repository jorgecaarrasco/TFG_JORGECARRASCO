-- =====================================================================
-- SCRIPT DE CREACIÓN DE TABLA - IMPRESORAS ZEBRA
-- Base de datos: incidencias_dashboard
-- Versión: 1.0
-- =====================================================================

USE incidencias_dashboard;

-- =====================================================================
-- TABLA: impresoras_zebra
-- Almacena la configuración de impresoras Zebra por puesto
-- =====================================================================
CREATE TABLE IF NOT EXISTS impresoras_zebra (
    -- Identificador único
    id INT AUTO_INCREMENT PRIMARY KEY,
    
    -- Ubicación de la impresora
    departamento VARCHAR(50) NOT NULL COMMENT 'packing, return, vas',
    puesto INT NOT NULL COMMENT 'Número del puesto (ej: 5 para PACK-05)',
    
    -- Datos de red
    ip VARCHAR(15) NOT NULL COMMENT 'Dirección IP de la impresora (ej: 10.59.63.105)',
    puerto INT DEFAULT 9100 COMMENT 'Puerto de comunicación ZPL (default 9100)',
    
    -- Información del dispositivo
    modelo VARCHAR(50) DEFAULT 'ZD420/ZD421' COMMENT 'Modelo de la impresora',
    descripcion VARCHAR(200) COMMENT 'Descripción adicional',
    
    -- Estado
    activo BOOLEAN DEFAULT TRUE COMMENT 'Si está activa o no',
    
    -- Configuración por defecto
    darkness_default INT DEFAULT 15 COMMENT 'Oscuridad por defecto (0-30)',
    speed_default INT DEFAULT 4 COMMENT 'Velocidad por defecto (2-6)',
    top_default INT DEFAULT 0 COMMENT 'Label Top por defecto (-30 a 30)',
    tear_off_default INT DEFAULT 0 COMMENT 'Tear Off por defecto (-30 a 30)',
    
    -- Auditoría
    fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP,
    fecha_actualizacion DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    -- Restricción única: un puesto solo puede tener una impresora
    UNIQUE KEY uk_dept_puesto (departamento, puesto),
    
    -- Índices para búsquedas rápidas
    INDEX idx_departamento (departamento),
    INDEX idx_activo (activo),
    INDEX idx_ip (ip)
    
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Configuración de impresoras Zebra por puesto de trabajo';

-- =====================================================================
-- INSERTAR DATOS INICIALES - PACKING (Puestos 4-60)
-- IP: 10.59.63.1XX donde XX = 100 + número de puesto
-- =====================================================================

-- Packing puestos 4 al 60
INSERT INTO impresoras_zebra (departamento, puesto, ip, modelo, descripcion) VALUES
('packing', 4, '10.59.63.104', 'ZD420/ZD421', 'Impresora Zebra Packing Puesto 4'),
('packing', 5, '10.59.63.105', 'ZD420/ZD421', 'Impresora Zebra Packing Puesto 5'),
('packing', 6, '10.59.63.106', 'ZD420/ZD421', 'Impresora Zebra Packing Puesto 6'),
('packing', 7, '10.59.63.107', 'ZD420/ZD421', 'Impresora Zebra Packing Puesto 7'),
('packing', 8, '10.59.63.108', 'ZD420/ZD421', 'Impresora Zebra Packing Puesto 8'),
('packing', 9, '10.59.63.109', 'ZD420/ZD421', 'Impresora Zebra Packing Puesto 9'),
('packing', 10, '10.59.63.110', 'ZD420/ZD421', 'Impresora Zebra Packing Puesto 10'),
('packing', 11, '10.59.63.111', 'ZD420/ZD421', 'Impresora Zebra Packing Puesto 11'),
('packing', 12, '10.59.63.112', 'ZD420/ZD421', 'Impresora Zebra Packing Puesto 12'),
('packing', 13, '10.59.63.113', 'ZD420/ZD421', 'Impresora Zebra Packing Puesto 13'),
('packing', 14, '10.59.63.114', 'ZD420/ZD421', 'Impresora Zebra Packing Puesto 14'),
('packing', 15, '10.59.63.115', 'ZD420/ZD421', 'Impresora Zebra Packing Puesto 15'),
('packing', 16, '10.59.63.116', 'ZD420/ZD421', 'Impresora Zebra Packing Puesto 16'),
('packing', 17, '10.59.63.117', 'ZD420/ZD421', 'Impresora Zebra Packing Puesto 17'),
('packing', 18, '10.59.63.118', 'ZD420/ZD421', 'Impresora Zebra Packing Puesto 18'),
('packing', 19, '10.59.63.119', 'ZD420/ZD421', 'Impresora Zebra Packing Puesto 19'),
('packing', 20, '10.59.63.120', 'ZD420/ZD421', 'Impresora Zebra Packing Puesto 20'),
('packing', 21, '10.59.63.121', 'ZD420/ZD421', 'Impresora Zebra Packing Puesto 21'),
('packing', 22, '10.59.63.122', 'ZD420/ZD421', 'Impresora Zebra Packing Puesto 22'),
('packing', 23, '10.59.63.123', 'ZD420/ZD421', 'Impresora Zebra Packing Puesto 23'),
('packing', 24, '10.59.63.124', 'ZD420/ZD421', 'Impresora Zebra Packing Puesto 24'),
('packing', 25, '10.59.63.125', 'ZD420/ZD421', 'Impresora Zebra Packing Puesto 25'),
('packing', 26, '10.59.63.126', 'ZD420/ZD421', 'Impresora Zebra Packing Puesto 26'),
('packing', 27, '10.59.63.127', 'ZD420/ZD421', 'Impresora Zebra Packing Puesto 27'),
('packing', 28, '10.59.63.128', 'ZD420/ZD421', 'Impresora Zebra Packing Puesto 28'),
('packing', 29, '10.59.63.129', 'ZD420/ZD421', 'Impresora Zebra Packing Puesto 29'),
('packing', 30, '10.59.63.130', 'ZD420/ZD421', 'Impresora Zebra Packing Puesto 30'),
('packing', 31, '10.59.63.131', 'ZD420/ZD421', 'Impresora Zebra Packing Puesto 31'),
('packing', 32, '10.59.63.132', 'ZD420/ZD421', 'Impresora Zebra Packing Puesto 32'),
('packing', 33, '10.59.63.133', 'ZD420/ZD421', 'Impresora Zebra Packing Puesto 33'),
('packing', 34, '10.59.63.134', 'ZD420/ZD421', 'Impresora Zebra Packing Puesto 34'),
('packing', 35, '10.59.63.135', 'ZD420/ZD421', 'Impresora Zebra Packing Puesto 35'),
('packing', 36, '10.59.63.136', 'ZD420/ZD421', 'Impresora Zebra Packing Puesto 36'),
('packing', 37, '10.59.63.137', 'ZD420/ZD421', 'Impresora Zebra Packing Puesto 37'),
('packing', 38, '10.59.63.138', 'ZD420/ZD421', 'Impresora Zebra Packing Puesto 38'),
('packing', 39, '10.59.63.139', 'ZD420/ZD421', 'Impresora Zebra Packing Puesto 39'),
('packing', 40, '10.59.63.140', 'ZD420/ZD421', 'Impresora Zebra Packing Puesto 40'),
('packing', 41, '10.59.63.141', 'ZD420/ZD421', 'Impresora Zebra Packing Puesto 41'),
('packing', 42, '10.59.63.142', 'ZD420/ZD421', 'Impresora Zebra Packing Puesto 42'),
('packing', 43, '10.59.63.143', 'ZD420/ZD421', 'Impresora Zebra Packing Puesto 43'),
('packing', 44, '10.59.63.144', 'ZD420/ZD421', 'Impresora Zebra Packing Puesto 44'),
('packing', 45, '10.59.63.145', 'ZD420/ZD421', 'Impresora Zebra Packing Puesto 45'),
('packing', 46, '10.59.63.146', 'ZD420/ZD421', 'Impresora Zebra Packing Puesto 46'),
('packing', 47, '10.59.63.147', 'ZD420/ZD421', 'Impresora Zebra Packing Puesto 47'),
('packing', 48, '10.59.63.148', 'ZD420/ZD421', 'Impresora Zebra Packing Puesto 48'),
('packing', 49, '10.59.63.149', 'ZD420/ZD421', 'Impresora Zebra Packing Puesto 49'),
('packing', 50, '10.59.63.150', 'ZD420/ZD421', 'Impresora Zebra Packing Puesto 50'),
('packing', 51, '10.59.63.151', 'ZD420/ZD421', 'Impresora Zebra Packing Puesto 51'),
('packing', 52, '10.59.63.152', 'ZD420/ZD421', 'Impresora Zebra Packing Puesto 52'),
('packing', 53, '10.59.63.153', 'ZD420/ZD421', 'Impresora Zebra Packing Puesto 53'),
('packing', 54, '10.59.63.154', 'ZD420/ZD421', 'Impresora Zebra Packing Puesto 54'),
('packing', 55, '10.59.63.155', 'ZD420/ZD421', 'Impresora Zebra Packing Puesto 55'),
('packing', 56, '10.59.63.156', 'ZD420/ZD421', 'Impresora Zebra Packing Puesto 56'),
('packing', 57, '10.59.63.157', 'ZD420/ZD421', 'Impresora Zebra Packing Puesto 57'),
('packing', 58, '10.59.63.158', 'ZD420/ZD421', 'Impresora Zebra Packing Puesto 58'),
('packing', 59, '10.59.63.159', 'ZD420/ZD421', 'Impresora Zebra Packing Puesto 59'),
('packing', 60, '10.59.63.160', 'ZD420/ZD421', 'Impresora Zebra Packing Puesto 60')
ON DUPLICATE KEY UPDATE 
    ip = VALUES(ip),
    fecha_actualizacion = CURRENT_TIMESTAMP;

-- =====================================================================
-- INSERTAR DATOS INICIALES - RETURN (Puestos 1-20)
-- IP: 10.59.63.X donde X = número de puesto
-- =====================================================================

INSERT INTO impresoras_zebra (departamento, puesto, ip, modelo, descripcion) VALUES
('return', 1, '10.59.63.1', 'ZD420/ZD421', 'Impresora Zebra Return Puesto 1'),
('return', 2, '10.59.63.2', 'ZD420/ZD421', 'Impresora Zebra Return Puesto 2'),
('return', 3, '10.59.63.3', 'ZD420/ZD421', 'Impresora Zebra Return Puesto 3'),
('return', 4, '10.59.63.4', 'ZD420/ZD421', 'Impresora Zebra Return Puesto 4'),
('return', 5, '10.59.63.5', 'ZD420/ZD421', 'Impresora Zebra Return Puesto 5'),
('return', 6, '10.59.63.6', 'ZD420/ZD421', 'Impresora Zebra Return Puesto 6'),
('return', 7, '10.59.63.7', 'ZD420/ZD421', 'Impresora Zebra Return Puesto 7'),
('return', 8, '10.59.63.8', 'ZD420/ZD421', 'Impresora Zebra Return Puesto 8'),
('return', 9, '10.59.63.9', 'ZD420/ZD421', 'Impresora Zebra Return Puesto 9'),
('return', 10, '10.59.63.10', 'ZD420/ZD421', 'Impresora Zebra Return Puesto 10'),
('return', 11, '10.59.63.11', 'ZD420/ZD421', 'Impresora Zebra Return Puesto 11'),
('return', 12, '10.59.63.12', 'ZD420/ZD421', 'Impresora Zebra Return Puesto 12'),
('return', 13, '10.59.63.13', 'ZD420/ZD421', 'Impresora Zebra Return Puesto 13'),
('return', 14, '10.59.63.14', 'ZD420/ZD421', 'Impresora Zebra Return Puesto 14'),
('return', 15, '10.59.63.15', 'ZD420/ZD421', 'Impresora Zebra Return Puesto 15'),
('return', 16, '10.59.63.16', 'ZD420/ZD421', 'Impresora Zebra Return Puesto 16'),
('return', 17, '10.59.63.17', 'ZD420/ZD421', 'Impresora Zebra Return Puesto 17'),
('return', 18, '10.59.63.18', 'ZD420/ZD421', 'Impresora Zebra Return Puesto 18'),
('return', 19, '10.59.63.19', 'ZD420/ZD421', 'Impresora Zebra Return Puesto 19'),
('return', 20, '10.59.63.20', 'ZD420/ZD421', 'Impresora Zebra Return Puesto 20')
ON DUPLICATE KEY UPDATE 
    ip = VALUES(ip),
    fecha_actualizacion = CURRENT_TIMESTAMP;

-- =====================================================================
-- INSERTAR DATOS INICIALES - VAS (Puestos 1-10)
-- IP: 10.59.63.2XX (TEMPORALES - CAMBIAR POR LAS REALES)
-- =====================================================================

INSERT INTO impresoras_zebra (departamento, puesto, ip, modelo, descripcion) VALUES
('vas', 1, '10.59.63.201', 'ZD420/ZD421', 'Impresora Zebra VAS Puesto 1 (IP TEMPORAL)'),
('vas', 2, '10.59.63.202', 'ZD420/ZD421', 'Impresora Zebra VAS Puesto 2 (IP TEMPORAL)'),
('vas', 3, '10.59.63.203', 'ZD420/ZD421', 'Impresora Zebra VAS Puesto 3 (IP TEMPORAL)'),
('vas', 4, '10.59.63.204', 'ZD420/ZD421', 'Impresora Zebra VAS Puesto 4 (IP TEMPORAL)'),
('vas', 5, '10.59.63.205', 'ZD420/ZD421', 'Impresora Zebra VAS Puesto 5 (IP TEMPORAL)'),
('vas', 6, '10.59.63.206', 'ZD420/ZD421', 'Impresora Zebra VAS Puesto 6 (IP TEMPORAL)'),
('vas', 7, '10.59.63.207', 'ZD420/ZD421', 'Impresora Zebra VAS Puesto 7 (IP TEMPORAL)'),
('vas', 8, '10.59.63.208', 'ZD420/ZD421', 'Impresora Zebra VAS Puesto 8 (IP TEMPORAL)'),
('vas', 9, '10.59.63.209', 'ZD420/ZD421', 'Impresora Zebra VAS Puesto 9 (IP TEMPORAL)'),
('vas', 10, '10.59.63.210', 'ZD420/ZD421', 'Impresora Zebra VAS Puesto 10 (IP TEMPORAL)')
ON DUPLICATE KEY UPDATE 
    ip = VALUES(ip),
    fecha_actualizacion = CURRENT_TIMESTAMP;

-- =====================================================================
-- INFORMACIÓN DEL SISTEMA
-- =====================================================================
SELECT 
    'Tabla impresoras_zebra creada/actualizada exitosamente' as mensaje,
    DATABASE() as base_datos,
    NOW() as fecha;

SELECT 
    departamento,
    COUNT(*) as total_impresoras,
    GROUP_CONCAT(puesto ORDER BY puesto) as puestos
FROM impresoras_zebra
WHERE activo = TRUE
GROUP BY departamento
ORDER BY departamento;

-- =====================================================================
-- FIN DEL SCRIPT
-- =====================================================================
