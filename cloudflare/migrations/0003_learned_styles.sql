-- Estils apresos de vídeos de referència («Aprèn l'estil»). Segura de repetir.
CREATE TABLE IF NOT EXISTS learned_styles (
 id TEXT PRIMARY KEY, label TEXT NOT NULL, profile TEXT NOT NULL, created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL
);
