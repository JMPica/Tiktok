CREATE TABLE IF NOT EXISTS uploads (
 id TEXT PRIMARY KEY, owner TEXT NOT NULL, filename TEXT NOT NULL,
 size_bytes INTEGER NOT NULL, r2_key TEXT NOT NULL, multipart_id TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'uploading', created_at INTEGER NOT NULL
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
 created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS job_output_parts (
 job_id TEXT NOT NULL REFERENCES jobs(id), part_no INTEGER NOT NULL,
 etag TEXT NOT NULL, size_bytes INTEGER NOT NULL,
 PRIMARY KEY(job_id, part_no)
);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status,created_at);
CREATE INDEX IF NOT EXISTS idx_jobs_owner ON jobs(owner,created_at);
