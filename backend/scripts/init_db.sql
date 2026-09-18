-- Script de inicialización de base de datos para MVP Baches RM
-- MySQL 8.x con soporte espacial

-- Crear base de datos si no existe
CREATE DATABASE IF NOT EXISTS baches_rm
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE baches_rm;

-- Tabla de comunas de la Región Metropolitana con geometría
DROP TABLE IF EXISTS resumen_comuna;
DROP TABLE IF EXISTS reportes_baches;
DROP TABLE IF EXISTS comunas_rm;

CREATE TABLE comunas_rm (
    codigo_comuna VARCHAR(10) PRIMARY KEY,
    nombre_comuna VARCHAR(100) NOT NULL,
    codigo_region VARCHAR(5) DEFAULT '13',
    geom GEOMETRY NOT NULL SRID 4326,
    SPATIAL INDEX idx_geom (geom)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tabla de reportes de baches
CREATE TABLE reportes_baches (
    id INT AUTO_INCREMENT PRIMARY KEY,
    lat DOUBLE NOT NULL,
    lon DOUBLE NOT NULL,
    punto POINT NOT NULL SRID 4326,
    codigo_comuna VARCHAR(10),
    direccion VARCHAR(255),
    comentario TEXT,
    severidad ENUM('baja', 'media', 'alta') DEFAULT 'media',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (codigo_comuna) REFERENCES comunas_rm(codigo_comuna),
    SPATIAL INDEX idx_punto (punto),
    INDEX idx_comuna (codigo_comuna),
    INDEX idx_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tabla caché de resúmenes generados por LLM
CREATE TABLE resumen_comuna (
    codigo_comuna VARCHAR(10) PRIMARY KEY,
    resumen_texto TEXT,
    top5_json JSON,
    generated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (codigo_comuna) REFERENCES comunas_rm(codigo_comuna)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Procedimiento para encontrar la comuna de un punto
DELIMITER //

CREATE PROCEDURE IF NOT EXISTS find_comuna_for_point(
    IN p_lon DOUBLE,
    IN p_lat DOUBLE,
    OUT p_codigo_comuna VARCHAR(10),
    OUT p_nombre_comuna VARCHAR(100)
)
BEGIN
    DECLARE v_point GEOMETRY;
    SET v_point = ST_SRID(POINT(p_lon, p_lat), 4326);

    SELECT codigo_comuna, nombre_comuna
    INTO p_codigo_comuna, p_nombre_comuna
    FROM comunas_rm
    WHERE ST_Contains(geom, v_point)
    LIMIT 1;
END //

DELIMITER ;

-- Vista para estadísticas por comuna
CREATE OR REPLACE VIEW v_estadisticas_comuna AS
SELECT
    c.codigo_comuna,
    c.nombre_comuna,
    COUNT(r.id) AS total_baches,
    SUM(CASE WHEN r.severidad = 'alta' THEN 1 ELSE 0 END) AS baches_alta,
    SUM(CASE WHEN r.severidad = 'media' THEN 1 ELSE 0 END) AS baches_media,
    SUM(CASE WHEN r.severidad = 'baja' THEN 1 ELSE 0 END) AS baches_baja,
    MAX(r.created_at) AS ultimo_reporte
FROM comunas_rm c
LEFT JOIN reportes_baches r ON c.codigo_comuna = r.codigo_comuna
GROUP BY c.codigo_comuna, c.nombre_comuna;
