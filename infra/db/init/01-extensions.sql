-- Runs once on first DB boot (docker-entrypoint-initdb.d). Idempotent.
CREATE EXTENSION IF NOT EXISTS vector;       -- pgvector for embeddings (FR-DI-2/5)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";  -- uuid_generate_v4 if needed
CREATE EXTENSION IF NOT EXISTS pg_trgm;      -- trigram search for fuzzy matching
