-- EXISTING D1 ONLY. Do not run after fresh schema.sql.
ALTER TABLE jobs ADD COLUMN style TEXT NOT NULL DEFAULT 'auto';
