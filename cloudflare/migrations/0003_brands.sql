-- Content Studio V4.1: dos marcas (Blau de Mar + Top House). SOLO para una base D1 ya desplegada con 0002_v4.sql.
-- Haz copia antes:  npx wrangler d1 export blau-tiktok-v3 --remote --output=backup-antes-0003.sql
-- No ejecutar sobre una base creada con el schema.sql actual (las columnas ya existen).
-- Todo lo existente queda asignado a Blau de Mar; no se mueve ni se borra ningún objeto de R2.
-- Rollback: el Worker anterior ignora la columna `brand`; basta con volver a desplegar la versión previa.
ALTER TABLE uploads ADD COLUMN brand TEXT NOT NULL DEFAULT 'blau_de_mar';
ALTER TABLE jobs ADD COLUMN brand TEXT NOT NULL DEFAULT 'blau_de_mar';
ALTER TABLE variants ADD COLUMN brand TEXT NOT NULL DEFAULT 'blau_de_mar';
CREATE INDEX IF NOT EXISTS idx_jobs_brand ON jobs(brand,created_at);
