-- =====================================================================
-- DATOS DE PRUEBA (DEMO) - DASHBOARD DE CONTROL IT
-- =====================================================================

USE incidencias_dashboard;

-- 1. LIMPIAR DATOS EXISTENTES (OPCIONAL)
-- SET FOREIGN_KEY_CHECKS = 0;
-- TRUNCATE TABLE comentarios_incidencias;
-- TRUNCATE TABLE historial_incidencias;
-- TRUNCATE TABLE incidencias;
-- SET FOREIGN_KEY_CHECKS = 1;

-- 2. INSERTAR USUARIOS DE PRUEBA
-- Nota: Las contraseñas en una app real deberían estar hasheadas. 
-- Aquí usamos las que espera el sistema en modo demo o las que se configuren.
INSERT INTO usuarios (username, password, nombre_completo, rol, departamento, activo) VALUES
('admin', 'admin123', 'Administrador de IT', 'IT_ADMIN', 'IT', 1),
('supervisor', 'super123', 'Supervisor de Turno', 'SUPERVISOR', 'OPERACIONES', 1),
('tecnico', 'tec123', 'Técnico de Soporte', 'TECNICO', 'IT', 1);

-- 3. INSERTAR MESAS DE PRUEBA (Si no existen en mesas.csv)
-- El sistema las carga desde MySQL si está disponible.
CREATE TABLE IF NOT EXISTS mesas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    departamento VARCHAR(50),
    puesto INT,
    ip VARCHAR(50),
    activa BOOLEAN DEFAULT 1
);

INSERT INTO mesas (departamento, puesto, ip) VALUES
('packing', 4, '192.168.1.4'),
('packing', 5, '192.168.1.5'),
('packing', 6, '192.168.1.6'),
('return', 1, '192.168.1.101'),
('return', 2, '192.168.1.102'),
('vas', 1, '192.168.1.201');

-- 4. INSERTAR INCIDENCIAS DE PRUEBA
INSERT INTO incidencias (departamento, puesto, categoria, descripcion, prioridad, estado, reportado_por, reportado_por_username) VALUES
('packing', 4, 'PC_NO_ENCIENDE', 'La torre no arranca tras un corte de luz', 'ALTA', 'pendiente', 'Operario 1', 'op1'),
('packing', 10, 'IMPRESORA', 'Atasco de etiquetas persistente', 'MEDIA', 'en_proceso', 'Operario 2', 'op2'),
('return', 2, 'RFID_ERROR', 'No lee ninguna etiqueta en el túnel', 'CRÍTICA', 'en_proceso', 'Supervisor 1', 'sup1'),
('vas', 1, 'PC_LENTO', 'La aplicación tarda mucho en cargar', 'BAJA', 'resuelta', 'Operario 3', 'op3');

-- 5. INSERTAR COMENTARIOS
INSERT INTO comentarios_incidencias (incidencia_id, usuario, username, comentario) VALUES
(2, 'Técnico de Soporte', 'tecnico', 'Revisando rodillos, parece que hay adhesivo pegado.'),
(3, 'Administrador de IT', 'admin', 'Reiniciando el PLC del túnel RFID.');

-- 6. INSERTAR IMPRESORAS ZEBRA DE PRUEBA
-- (Según esquema de add_impresoras_zebra.sql)
INSERT INTO impresoras_zebra (departamento, puesto, ip, puerto, modelo) VALUES
('packing', 4, '192.168.1.236', 9100, 'ZD421'),
('packing', 5, '192.168.1.74', 9100, 'ZD420'),
('return', 1, '192.168.1.217', 9100, 'ZD421');
