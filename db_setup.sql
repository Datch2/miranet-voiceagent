-- SQL Script for MySQL Workbench
-- Miranet VoiceAgent Database Setup and Synthetic Data

-- 1. Create Database if it doesn't exist
CREATE DATABASE IF NOT EXISTS `miranet_voiceagent`
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;

USE `miranet_voiceagent`;

-- 2. Drop existing tables in reverse dependency order (to prevent key constraint errors)
DROP TABLE IF EXISTS `reportes_tecnicos`;
DROP TABLE IF EXISTS `incidencias`;
DROP TABLE IF EXISTS `clientes`;
DROP TABLE IF EXISTS `equipos_red`;
DROP TABLE IF EXISTS `zonas`;
DROP TABLE IF EXISTS `network_metrics`;
DROP TABLE IF EXISTS `voice_logs`;
DROP TABLE IF EXISTS `conversations`;

-- 3. Create Tables
CREATE TABLE IF NOT EXISTS `conversations` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `session_id` VARCHAR(255) UNIQUE NOT NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS `voice_logs` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `session_id` VARCHAR(255) NOT NULL,
    `sequence_number` INT NOT NULL,
    `audio_size_bytes` INT NOT NULL,
    `transcription` TEXT,
    `classification_intent` VARCHAR(255),
    `classification_sentiment` VARCHAR(255),
    `response_text` TEXT,
    `transcription_latency_ms` INT,
    `classification_latency_ms` INT,
    `response_latency_ms` INT,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (`session_id`) REFERENCES `conversations`(`session_id`) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS `network_metrics` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `session_id` VARCHAR(255) NOT NULL,
    `latency_ms` INT,
    `packet_loss_rate` FLOAT,
    `jitter_ms` INT,
    `bandwidth_kbps` FLOAT,
    `recorded_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (`session_id`) REFERENCES `conversations`(`session_id`) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS `zonas` (
    `id` INT PRIMARY KEY,
    `nombre` VARCHAR(255) UNIQUE NOT NULL,
    `estado` VARCHAR(255) NOT NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS `equipos_red` (
    `id` INT PRIMARY KEY,
    `nombre` VARCHAR(255) UNIQUE NOT NULL,
    `zona_id` INT NOT NULL,
    `cpu_usage` FLOAT NOT NULL,
    `mem_usage` FLOAT NOT NULL,
    `packet_loss` FLOAT NOT NULL,
    `interface_status` VARCHAR(255) NOT NULL,
    FOREIGN KEY (`zona_id`) REFERENCES `zonas`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS `clientes` (
    `id` INT PRIMARY KEY,
    `nombre` VARCHAR(255) NOT NULL,
    `dni` VARCHAR(255) UNIQUE NOT NULL,
    `router_sn` VARCHAR(255) UNIQUE NOT NULL,
    `zona_id` INT NOT NULL,
    FOREIGN KEY (`zona_id`) REFERENCES `zonas`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS `incidencias` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `session_id` VARCHAR(255) NOT NULL,
    `cliente_id` INT NOT NULL,
    `descripcion` TEXT,
    `nivel_gravedad` VARCHAR(255),
    `estado` VARCHAR(255),
    `creado_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (`session_id`) REFERENCES `conversations`(`session_id`) ON DELETE CASCADE,
    FOREIGN KEY (`cliente_id`) REFERENCES `clientes`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS `reportes_tecnicos` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `incidencia_id` INT NOT NULL,
    `diagnostico` TEXT,
    `confianza` FLOAT,
    `detalles_tecnicos` TEXT,
    `creado_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (`incidencia_id`) REFERENCES `incidencias`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 4. Seed Mock Data
-- Zonas
INSERT INTO `zonas` (`id`, `nombre`, `estado`) VALUES
(1, 'Norte', 'falla_individual'),
(2, 'Sur', 'operativo'),
(3, 'Centro', 'falla_masiva'),
(4, 'Este', 'operativo');

-- Equipos de Red (SNMP Mock)
INSERT INTO `equipos_red` (`id`, `nombre`, `zona_id`, `cpu_usage`, `mem_usage`, `packet_loss`, `interface_status`) VALUES
(1, 'Router-Norte-01', 1, 88.0, 75.0, 4.5, 'up'),
(2, 'Router-Sur-01', 2, 25.0, 40.0, 0.0, 'up'),
(3, 'Router-Centro-01', 3, 99.0, 95.0, 15.0, 'down'),
(4, 'Router-Este-01', 4, 30.0, 45.0, 0.0, 'up');

-- Clientes
INSERT INTO `clientes` (`id`, `nombre`, `dni`, `router_sn`, `zona_id`) VALUES
(1, 'Diego Torres', '12345678', 'RT000001', 1),
(2, 'Sergio Perez', '87654321', 'RT000002', 2),
(3, 'Maria Gomez', '11112222', 'RT000003', 3),
(4, 'Juan Lopez', '33334444', 'RT000004', 4);

-- 5. Insert Initial Test Conversation, Incident, and Report
INSERT INTO `conversations` (`session_id`) VALUES ('session_workbench_test');

INSERT INTO `incidencias` (`id`, `session_id`, `cliente_id`, `descripcion`, `nivel_gravedad`, `estado`) VALUES
(1, 'session_workbench_test', 3, 'Mi router tiene la luz roja y mis vecinos tampoco tienen internet', 'critico', 'diagnosticando');

INSERT INTO `reportes_tecnicos` (`id`, `incidencia_id`, `diagnostico`, `confianza`, `detalles_tecnicos`) VALUES
(1, 1, 'Avería Masiva en Zona Centro: Router-Centro-01 con interfaz DOWN y 15% packet loss', 99.0, '{"zona": "Centro", "equipo": "Router-Centro-01", "interface": "down"}');
