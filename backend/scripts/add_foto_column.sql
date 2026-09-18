-- Agregar columna foto_url a la tabla reportes_baches
-- Ejecutar este script en MySQL

ALTER TABLE reportes_baches
ADD COLUMN foto_url VARCHAR(500) NULL AFTER severidad;

-- Verificar que se agregó correctamente
DESCRIBE reportes_baches;
