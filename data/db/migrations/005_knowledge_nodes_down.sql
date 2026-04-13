-- 005 rollback — reverse knowledge_nodes migration
BEGIN;

-- Remove migrated columns from knowledge_entries
ALTER TABLE knowledge_entries
    DROP COLUMN IF EXISTS migrated_to_node_id,
    DROP COLUMN IF EXISTS migrated;

-- Remove node_id from knowledge_terms
DROP INDEX IF EXISTS idx_knowledge_terms_node;
ALTER TABLE knowledge_terms
    DROP COLUMN IF EXISTS node_id;

-- Drop revisions table (before nodes, due to FK)
DROP TABLE IF EXISTS knowledge_node_revisions;

-- Drop nodes table
DROP TABLE IF EXISTS knowledge_nodes;

-- Remove migration record
DELETE FROM schema_migrations WHERE version = '005_knowledge_nodes';

COMMIT;
