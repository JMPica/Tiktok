-- Blau de Mar TikTok Studio V4 · D1 (base NUEVA). Para una base V3 existente usa migrations/0002_v4.sql.
CREATE TABLE IF NOT EXISTS uploads (
 id TEXT PRIMARY KEY, owner TEXT NOT NULL, filename TEXT NOT NULL,
 size_bytes INTEGER NOT NULL, r2_key TEXT NOT NULL, multipart_id TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'uploading', created_at INTEGER NOT NULL,
 completed_at INTEGER, consent_team INTEGER NOT NULL DEFAULT 0, analysis_key TEXT
);
CREATE TABLE IF NOT EXISTS upload_parts (
 upload_id TEXT NOT NULL REFERENCES uploads(id), part_no INTEGER NOT NULL,
 etag TEXT NOT NULL, size_bytes INTEGER NOT NULL,
 PRIMARY KEY(upload_id, part_no)
);
CREATE TABLE IF NOT EXISTS jobs (
 id TEXT PRIMARY KEY, upload_id TEXT NOT NULL REFERENCES uploads(id),
 owner TEXT NOT NULL, mode TEXT NOT NULL, style TEXT NOT NULL DEFAULT 'auto', status TEXT NOT NULL,
 r2_key TEXT, result_sha256 TEXT, qc TEXT, error TEXT,
 lease_until INTEGER, agent_id TEXT, output_multipart_id TEXT,
 approved_by TEXT, approved_sha256 TEXT, approved_at INTEGER,
 created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL,
 kind TEXT NOT NULL DEFAULT 'produce', language TEXT NOT NULL DEFAULT 'ca', options TEXT,
 parent_variant_id TEXT, instruction TEXT, manual_edits TEXT,
 stage TEXT, progress INTEGER NOT NULL DEFAULT 0, message TEXT,
 attempts INTEGER NOT NULL DEFAULT 0, finished_at INTEGER, summary TEXT
);
CREATE TABLE IF NOT EXISTS job_output_parts (
 job_id TEXT NOT NULL REFERENCES jobs(id), part_no INTEGER NOT NULL,
 etag TEXT NOT NULL, size_bytes INTEGER NOT NULL,
 PRIMARY KEY(job_id, part_no)
);
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
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status,created_at);
CREATE INDEX IF NOT EXISTS idx_jobs_owner ON jobs(owner,created_at);
CREATE INDEX IF NOT EXISTS idx_variants_job ON variants(job_id,idx);
CREATE INDEX IF NOT EXISTS idx_variants_upload ON variants(upload_id);
CREATE INDEX IF NOT EXISTS idx_uploads_owner ON uploads(owner,created_at);
