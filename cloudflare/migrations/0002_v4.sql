-- SOLO para una base D1 V3 ya desplegada (con 0001_add_style.sql aplicada). Haz copia antes:
--   npx wrangler d1 export blau-tiktok-v3 --remote --output=backup-v3.sql
-- No ejecutar sobre una base creada con el schema.sql V4 (las columnas ya existen).
ALTER TABLE uploads ADD COLUMN completed_at INTEGER;
ALTER TABLE uploads ADD COLUMN consent_team INTEGER NOT NULL DEFAULT 0;
ALTER TABLE uploads ADD COLUMN analysis_key TEXT;
ALTER TABLE jobs ADD COLUMN kind TEXT NOT NULL DEFAULT 'produce';
ALTER TABLE jobs ADD COLUMN language TEXT NOT NULL DEFAULT 'ca';
ALTER TABLE jobs ADD COLUMN options TEXT;
ALTER TABLE jobs ADD COLUMN parent_variant_id TEXT;
ALTER TABLE jobs ADD COLUMN instruction TEXT;
ALTER TABLE jobs ADD COLUMN manual_edits TEXT;
ALTER TABLE jobs ADD COLUMN stage TEXT;
ALTER TABLE jobs ADD COLUMN progress INTEGER NOT NULL DEFAULT 0;
ALTER TABLE jobs ADD COLUMN message TEXT;
ALTER TABLE jobs ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0;
ALTER TABLE jobs ADD COLUMN finished_at INTEGER;
ALTER TABLE jobs ADD COLUMN summary TEXT;
CREATE TABLE IF NOT EXISTS variants (
 id TEXT PRIMARY KEY, job_id TEXT NOT NULL REFERENCES jobs(id), upload_id TEXT NOT NULL REFERENCES uploads(id),
 owner TEXT NOT NULL, idx INTEGER NOT NULL, version INTEGER NOT NULL DEFAULT 1, parent_variant_id TEXT,
 title TEXT, style TEXT, status TEXT NOT NULL, r2_key TEXT, poster_key TEXT, edl_key TEXT,
 output_multipart_id TEXT, size_bytes INTEGER, sha256 TEXT, qc TEXT, explanation TEXT,
 score_total INTEGER, risks TEXT, requires TEXT, duration REAL,
 approved_by TEXT, approved_sha256 TEXT, approved_at INTEGER, approval_checklist TEXT,
 reviewed_by TEXT, review_note TEXT, created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS variant_parts (
 variant_id TEXT NOT NULL REFERENCES variants(id), part_no INTEGER NOT NULL,
 etag TEXT NOT NULL, size_bytes INTEGER NOT NULL,
 PRIMARY KEY(variant_id, part_no)
);
CREATE TABLE IF NOT EXISTS audit (
 id INTEGER PRIMARY KEY AUTOINCREMENT, at INTEGER NOT NULL, actor TEXT NOT NULL,
 action TEXT NOT NULL, target TEXT, detail TEXT
);
-- Los renders V3 (una salida por job) pasan a ser la variante 0 de su job.
INSERT INTO variants (id,job_id,upload_id,owner,idx,version,title,style,status,r2_key,sha256,qc,
  approved_by,approved_sha256,approved_at,created_at,updated_at)
SELECT id,id,upload_id,owner,0,1,'V3',style,status,r2_key,result_sha256,qc,approved_by,approved_sha256,approved_at,created_at,updated_at
FROM jobs WHERE r2_key IS NOT NULL AND status IN ('needs_approval','approved','rejected');
UPDATE jobs SET status='done' WHERE status IN ('needs_approval','approved','rejected') AND r2_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_variants_job ON variants(job_id,idx);
CREATE INDEX IF NOT EXISTS idx_variants_upload ON variants(upload_id);
CREATE INDEX IF NOT EXISTS idx_uploads_owner ON uploads(owner,created_at);
