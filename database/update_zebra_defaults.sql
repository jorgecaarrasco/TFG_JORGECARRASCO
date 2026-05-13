-- =====================================================================
-- SCRIPT DE ACTUALIZACIÓN - VALORES PREDETERMINADOS IMPRESORAS ZEBRA
-- Base de datos: incidencias_dashboard
-- Fecha: 2025-12-28
-- Autor: IT Admin
-- =====================================================================

USE incidencias_dashboard;

-- =====================================================================
-- PASO 1: Actualizar estructura de tabla para incluir nuevos campos
-- =====================================================================

-- Añadir campo para contraste personalizado (si se necesita un valor diferente a 5)
ALTER TABLE impresoras_zebra 
ADD COLUMN IF NOT EXISTS darkness_custom INT DEFAULT NULL COMMENT 'Contraste personalizado fijo (NULL = usar default 5)',
ADD COLUMN IF NOT EXISTS left_position INT DEFAULT NULL COMMENT 'Posición izquierda personalizada',
ADD COLUMN IF NOT EXISTS top_position INT DEFAULT NULL COMMENT 'Posición superior personalizada',
ADD COLUMN IF NOT EXISTS custom_locked BOOLEAN DEFAULT FALSE COMMENT 'Si está bloqueada con configuración personalizada';

-- =====================================================================
-- PASO 2: Actualizar valores predeterminados según especificaciones
-- =====================================================================

-- CONTRASTE: Todas las impresoras deben tener contraste predeterminado en 5
UPDATE impresoras_zebra 
SET darkness_default = 5
WHERE darkness_default != 5 OR darkness_default IS NULL;

-- POSICIÓN SUPERIOR: Todas las impresoras en 0
UPDATE impresoras_zebra 
SET top_default = 0
WHERE top_default != 0 OR top_default IS NULL;

-- POSICIÓN IZQUIERDA: Packing = 0, Return = -215, VAS = -215
UPDATE impresoras_zebra 
SET tear_off_default = 0
WHERE departamento = 'packing';

UPDATE impresoras_zebra 
SET tear_off_default = -215
WHERE departamento IN ('return', 'vas');

-- =====================================================================
-- PASO 3: Resetear configuraciones personalizadas (opcional)
-- Solo descomentar si se desea borrar todas las personalizaciones
-- =====================================================================

-- UPDATE impresoras_zebra 
-- SET darkness_custom = NULL,
--     left_position = NULL,
--     top_position = NULL,
--     custom_locked = FALSE;

-- =====================================================================
-- PASO 4: Verificación de configuración
-- =====================================================================

SELECT 
    departamento,
    COUNT(*) as total_impresoras,
    AVG(darkness_default) as contraste_promedio,
    MIN(tear_off_default) as pos_izq_minima,
    MAX(tear_off_default) as pos_izq_maxima,
    AVG(top_default) as pos_superior_promedio
FROM impresoras_zebra
WHERE activo = TRUE
GROUP BY departamento
ORDER BY departamento;

SELECT 
    'Configuración actualizada correctamente' as mensaje,
    DATABASE() as base_datos,
    NOW() as fecha;

-- =====================================================================
-- INFORMACIÓN: Configuraciones esperadas
-- =====================================================================
-- PACKING:
--   - Contraste (darkness): 5 (predeterminado)
--   - Posición izquierda (tear_off): 0
--   - Posición superior (top): 0
--
-- RETURN:
--   - Contraste (darkness): 5 (predeterminado)
--   - Posición izquierda (tear_off): -215
--   - Posición superior (top): 0
--
-- VAS:
--   - Contraste (darkness): 5 (predeterminado)
--   - Posición izquierda (tear_off): -215
--   - Posición superior (top): 0
--
-- NOTA: Las impresoras pueden tener contraste personalizado (darkness_custom)
--       que se usará en lugar del predeterminado si custom_locked = TRUE
-- =====================================================================
