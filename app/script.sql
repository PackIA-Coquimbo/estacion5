-- Esquema de persistencia v2. La aplicación crea estas tablas con SQLAlchemy.
-- Este archivo se conserva como referencia para instalaciones manuales.

CREATE TABLE IF NOT EXISTS lote (
    id_lote VARCHAR(50) PRIMARY KEY,
    fecha_creacion DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    estado VARCHAR(20) NOT NULL DEFAULT 'activo'
        CHECK (estado IN ('activo', 'finalizado', 'pausado'))
);

CREATE TABLE IF NOT EXISTS grupo (
    id_grupo VARCHAR(100) PRIMARY KEY,
    id_lote VARCHAR(50) NOT NULL REFERENCES lote(id_lote) ON DELETE CASCADE,
    frutas_detectadas INTEGER,
    e1_validez_imagen BOOLEAN,
    e1_estado_captura VARCHAR(30),
    e1_posicion_correcta BOOLEAN,
    estado VARCHAR(30) NOT NULL DEFAULT 'en_proceso',
    ingreso DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    salida DATETIME
);

CREATE TABLE IF NOT EXISTS fruta (
    id INTEGER PRIMARY KEY,
    id_grupo VARCHAR(100) NOT NULL REFERENCES grupo(id_grupo) ON DELETE CASCADE,
    id_fruta VARCHAR(100) NOT NULL,
    e2_calidad_visual VARCHAR(40),
    e2_confianza_visual REAL,
    e2_defectos JSON,
    e3_diametro_mm REAL,
    e3_tamano VARCHAR(20),
    e4_categoria_final VARCHAR(40),
    e4_probabilidad REAL,
    e4_revision_manual BOOLEAN,
    CONSTRAINT uq_fruta_grupo_id UNIQUE (id_grupo, id_fruta)
);

CREATE TABLE IF NOT EXISTS lectura (
    id INTEGER PRIMARY KEY,
    id_lote VARCHAR(50) NOT NULL REFERENCES lote(id_lote) ON DELETE CASCADE,
    id_grupo VARCHAR(100) REFERENCES grupo(id_grupo) ON DELETE SET NULL,
    estacion VARCHAR(2) NOT NULL,
    ts_estacion DATETIME NOT NULL,
    ts_recepcion DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    payload JSON NOT NULL,
    payload_hash VARCHAR(64) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS alerta (
    id INTEGER PRIMARY KEY,
    id_lote VARCHAR(50) NOT NULL REFERENCES lote(id_lote) ON DELETE CASCADE,
    id_grupo VARCHAR(100),
    id_fruta VARCHAR(100),
    estacion VARCHAR(2) NOT NULL,
    severidad VARCHAR(20) NOT NULL,
    mensaje VARCHAR(300) NOT NULL,
    creado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resuelta BOOLEAN NOT NULL DEFAULT FALSE,
    dedupe_key VARCHAR(200) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS evento_cinta (
    id INTEGER PRIMARY KEY,
    id_lote VARCHAR(50) NOT NULL REFERENCES lote(id_lote) ON DELETE CASCADE,
    lectura_id INTEGER NOT NULL UNIQUE REFERENCES lectura(id) ON DELETE CASCADE,
    estado_cinta VARCHAR(30) NOT NULL,
    falla_mecanica BOOLEAN NOT NULL,
    id_grupo_en_cinta VARCHAR(100),
    ts DATETIME NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_grupo_id_lote ON grupo(id_lote);
CREATE INDEX IF NOT EXISTS ix_lectura_estacion_ts
    ON lectura(estacion, ts_recepcion);
CREATE INDEX IF NOT EXISTS ix_lectura_lote_grupo
    ON lectura(id_lote, id_grupo);
CREATE INDEX IF NOT EXISTS ix_alerta_activa
    ON alerta(resuelta, creado_en);
