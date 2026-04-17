-- Rollback 006: Remove structured UL fields
BEGIN;

DROP INDEX IF EXISTS idx_knowledge_terms_aggregate_root;
DROP INDEX IF EXISTS idx_knowledge_terms_type;

ALTER TABLE knowledge_terms
    DROP CONSTRAINT IF EXISTS knowledge_terms_type_check;

ALTER TABLE knowledge_terms
    DROP COLUMN IF EXISTS related_terms,
    DROP COLUMN IF EXISTS notes,
    DROP COLUMN IF EXISTS examples,
    DROP COLUMN IF EXISTS business_rules,
    DROP COLUMN IF EXISTS related_entities,
    DROP COLUMN IF EXISTS aggregate_root,
    DROP COLUMN IF EXISTS definition,
    DROP COLUMN IF EXISTS type;

DELETE FROM schema_migrations WHERE version = '006_knowledge_terms_structured';

COMMIT;
