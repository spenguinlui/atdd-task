-- Rollback 007: Remove source format CHECK
BEGIN;

ALTER TABLE knowledge_terms
    DROP CONSTRAINT IF EXISTS knowledge_terms_source_format_check;

DELETE FROM schema_migrations WHERE version = '007_knowledge_terms_source_check';

COMMIT;
