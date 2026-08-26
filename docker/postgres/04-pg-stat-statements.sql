-- E-OBS-PG-SRE: extensión para Top-N slow queries (initdb fresco).
-- Volúmenes ya existentes: ensure_pg_grants.py + shared_preload en compose.
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
