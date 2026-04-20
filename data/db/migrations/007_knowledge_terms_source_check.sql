-- 007 Knowledge Terms — source 欄位格式 CHECK
-- 規範 source 值的合法格式，同時保留 NULL（legacy）與前綴擴展性（code:*, claude:*, slack:*）
BEGIN;

ALTER TABLE knowledge_terms
    ADD CONSTRAINT knowledge_terms_source_format_check
    CHECK (
        source IS NULL
        OR source ~ '^(ul\.md(→migration)?|domain-name|code(:.+)?|claude:.+|slack(:.+)?|curator|user)$'
    );

COMMENT ON COLUMN knowledge_terms.source IS
    'Lineage of this term. Allowed: ul.md, ul.md→migration, domain-name, code[:path], claude:{agent/context}, slack[:channel], curator, user, or NULL.';

INSERT INTO schema_migrations (version) VALUES ('007_knowledge_terms_source_check');

COMMIT;
