-- Phase 3-2: Extend task_status enum with ATDD pipeline names
-- Existing Slack Bot values (pending_spec, specifying, etc.) remain valid.

-- NOTE: ALTER TYPE ... ADD VALUE cannot run inside a transaction block.
-- Each ADD VALUE is its own implicit transaction.

ALTER TYPE task_status ADD VALUE IF NOT EXISTS 'requirement' BEFORE 'pending_spec';
ALTER TYPE task_status ADD VALUE IF NOT EXISTS 'specification' AFTER 'requirement';
ALTER TYPE task_status ADD VALUE IF NOT EXISTS 'testing' AFTER 'specification';
ALTER TYPE task_status ADD VALUE IF NOT EXISTS 'development' AFTER 'testing';
ALTER TYPE task_status ADD VALUE IF NOT EXISTS 'review' AFTER 'development';
ALTER TYPE task_status ADD VALUE IF NOT EXISTS 'failed' AFTER 'aborted';

-- Record migration (must be separate since ADD VALUE can't be in transaction)
INSERT INTO schema_migrations (version) VALUES ('002_extend_task_status')
ON CONFLICT DO NOTHING;
