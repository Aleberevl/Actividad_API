-- MySQL dump (SAFE) para dofdb

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!50503 SET NAMES utf8mb4 */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

-- Si tu servidor no usa GTID, deja comentado:
-- /* SET @@GLOBAL.GTID_PURGED='92514259-bb44-11f0-8317-ce346530e72d:1-32'; */

CREATE DATABASE IF NOT EXISTS dofdb CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE dofdb;

SET SQL_MODE='';
SET FOREIGN_KEY_CHECKS=0;

-- ------------------------------------------------------
-- Tabla: entities
-- ------------------------------------------------------
DROP TABLE IF EXISTS entities;
CREATE TABLE entities (
  id BIGINT NOT NULL AUTO_INCREMENT,
  name VARCHAR(255) NOT NULL,
  type ENUM('Ley','Reglamento','rgano','Persona','Ubicacin','Otro') NOT NULL,
  norm_name VARCHAR(255) NOT NULL,
  PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ------------------------------------------------------
-- Tabla: exports
-- ------------------------------------------------------
DROP TABLE IF EXISTS exports;
CREATE TABLE exports (
  id BIGINT NOT NULL AUTO_INCREMENT,
  user_id BIGINT NOT NULL,
  format ENUM('PDF','DOCX','JSON','CSV') NOT NULL,
  status ENUM('pending','processing','completed','failed') NOT NULL,
  storage_uri TEXT,
  created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ------------------------------------------------------
-- Tabla: publications
-- ------------------------------------------------------
DROP TABLE IF EXISTS publications;
CREATE TABLE publications (
  id BIGINT NOT NULL AUTO_INCREMENT,
  dof_date DATE NOT NULL,
  issue_number VARCHAR(100) DEFAULT NULL,
  type ENUM('DOF','Extra','Alcance','Otro') NOT NULL,
  source_url TEXT NOT NULL,
  sha256 VARCHAR(64) DEFAULT NULL,
  published_at TIMESTAMP NULL DEFAULT NULL,
  fetched_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  status ENUM('fetched','parsed','summarized','failed') NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY sha256 (sha256),
  KEY idx_publications_dof_date (dof_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ------------------------------------------------------
-- Tabla: files (incluye public_url)
-- ------------------------------------------------------
DROP TABLE IF EXISTS files;
CREATE TABLE files (
  id BIGINT NOT NULL AUTO_INCREMENT,
  publication_id BIGINT NOT NULL,
  storage_uri TEXT NOT NULL,
  public_url TEXT DEFAULT NULL,              -- URL pública/descargable del PDF
  mime VARCHAR(50) NOT NULL,
  bytes BIGINT DEFAULT NULL,
  sha256 VARCHAR(64) DEFAULT NULL,
  has_ocr TINYINT(1) NOT NULL DEFAULT 0,
  pages_count INT NOT NULL DEFAULT 0,
  PRIMARY KEY (id),
  UNIQUE KEY sha256 (sha256),
  KEY idx_files_pub_date (publication_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ------------------------------------------------------
-- Tabla: pages
-- ------------------------------------------------------
DROP TABLE IF EXISTS pages;
CREATE TABLE pages (
  id BIGINT NOT NULL AUTO_INCREMENT,
  file_id BIGINT NOT NULL,
  page_no INT NOT NULL,
  text MEDIUMTEXT,
  tsv MEDIUMTEXT,
  image_uri TEXT,
  checksum VARCHAR(100) DEFAULT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_pages_file_page (file_id, page_no)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ------------------------------------------------------
-- Tabla: sections
-- ------------------------------------------------------
DROP TABLE IF EXISTS sections;
CREATE TABLE sections (
  id BIGINT NOT NULL AUTO_INCREMENT,
  publication_id BIGINT NOT NULL,
  name VARCHAR(255) NOT NULL,
  seq INT NOT NULL,
  page_start INT DEFAULT NULL,
  page_end INT DEFAULT NULL,
  PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ------------------------------------------------------
-- Tabla: items
-- ------------------------------------------------------
DROP TABLE IF EXISTS items;
CREATE TABLE items (
  id BIGINT NOT NULL AUTO_INCREMENT,
  section_id BIGINT NOT NULL,
  item_type ENUM('Decreto','Acuerdo','Aviso','Licitacin','Otro') NOT NULL,
  title TEXT NOT NULL,
  issuing_entity TEXT,
  reference_code VARCHAR(100) DEFAULT NULL,
  page_from INT DEFAULT NULL,
  page_to INT DEFAULT NULL,
  raw_text MEDIUMTEXT,
  tsv MEDIUMTEXT,
  ingested_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ------------------------------------------------------
-- Tabla: item_entities
-- ------------------------------------------------------
DROP TABLE IF EXISTS item_entities;
CREATE TABLE item_entities (
  item_id BIGINT NOT NULL,
  entity_id BIGINT NOT NULL,
  evidence_span TEXT,
  PRIMARY KEY (item_id, entity_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ------------------------------------------------------
-- Tabla: summaries
-- ------------------------------------------------------
DROP TABLE IF EXISTS summaries;
CREATE TABLE summaries (
  id BIGINT NOT NULL AUTO_INCREMENT,
  object_type ENUM('publication','section','item','chunk') NOT NULL,
  object_id BIGINT NOT NULL,
  model VARCHAR(100) NOT NULL,
  model_version VARCHAR(50) DEFAULT NULL,
  lang VARCHAR(10) DEFAULT NULL,
  summary_text MEDIUMTEXT NOT NULL,
  confidence DECIMAL(5,4) DEFAULT NULL,
  created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  created_by BIGINT DEFAULT NULL,
  PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ------------------------------------------------------
-- Tabla: ingestion_jobs
-- ------------------------------------------------------
DROP TABLE IF EXISTS ingestion_jobs;
CREATE TABLE ingestion_jobs (
  id BIGINT NOT NULL AUTO_INCREMENT,
  run_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  source ENUM('crawler','manual_upload') NOT NULL,
  status ENUM('running','completed','failed') NOT NULL,
  PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ------------------------------------------------------
-- Tabla: retention_queue
-- ------------------------------------------------------
DROP TABLE IF EXISTS retention_queue;
CREATE TABLE retention_queue (
  id BIGINT NOT NULL AUTO_INCREMENT,
  object_type VARCHAR(50) NOT NULL,
  object_id BIGINT NOT NULL,
  delete_after TIMESTAMP NOT NULL,
  reason ENUM('ttl_24h','user_request') NOT NULL,
  PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ------------------------------------------------------
-- Tabla: tasks
-- ------------------------------------------------------
DROP TABLE IF EXISTS tasks;
CREATE TABLE tasks (
  id BIGINT NOT NULL AUTO_INCREMENT,
  publication_id BIGINT NOT NULL,
  task_type ENUM('parse_pdf','ocr','split','nlp','summarize','index') NOT NULL,
  status ENUM('queued','running','done','failed') NOT NULL,
  started_at TIMESTAMP NULL DEFAULT NULL,
  finished_at TIMESTAMP NULL DEFAULT NULL,
  retries INT DEFAULT 0,
  error TEXT,
  PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ------------------------------------------------------
-- Tabla: users
-- ------------------------------------------------------
DROP TABLE IF EXISTS users;
CREATE TABLE users (
  id BIGINT NOT NULL AUTO_INCREMENT,
  email VARCHAR(255) NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  full_name VARCHAR(255) NOT NULL,
  status ENUM('active','suspended','pending') DEFAULT 'pending',
  role ENUM('admin','reader','processor') DEFAULT 'reader',
  created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  last_login_at TIMESTAMP NULL DEFAULT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_users_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

SET FOREIGN_KEY_CHECKS=1;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;
