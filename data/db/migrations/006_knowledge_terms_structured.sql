-- 006 Knowledge Terms — 結構化 UL（對齊 knowledge/schemas/ul-entry.yml）
-- 策略：additive。context 欄位保留標記 deprecated，現有資料不動。
BEGIN;

ALTER TABLE knowledge_terms
    ADD COLUMN type             TEXT NOT NULL DEFAULT 'Concept',
    ADD COLUMN definition       TEXT,
    ADD COLUMN aggregate_root   TEXT,
    ADD COLUMN related_entities TEXT[] NOT NULL DEFAULT '{}',
    ADD COLUMN business_rules   TEXT[] NOT NULL DEFAULT '{}',
    ADD COLUMN examples         TEXT[] NOT NULL DEFAULT '{}',
    ADD COLUMN notes            TEXT[] NOT NULL DEFAULT '{}',
    ADD COLUMN related_terms    TEXT[] NOT NULL DEFAULT '{}';

ALTER TABLE knowledge_terms
    ADD CONSTRAINT knowledge_terms_type_check
    CHECK (type IN ('Entity', 'ValueObject', 'Aggregate', 'Service', 'Event', 'Concept'));

CREATE INDEX idx_knowledge_terms_type ON knowledge_terms (org_id, project, type);
CREATE INDEX idx_knowledge_terms_aggregate_root ON knowledge_terms (org_id, project, aggregate_root);

COMMENT ON COLUMN knowledge_terms.context IS
    'DEPRECATED: legacy free-text. New writes should populate definition/examples/notes/related_terms.';
COMMENT ON COLUMN knowledge_terms.type IS
    'DDD classification: Entity, ValueObject, Aggregate, Service, Event, Concept.';
COMMENT ON COLUMN knowledge_terms.business_rules IS
    'Business rule IDs referencing this term, format: {VR|CR|ST|CA|AU|TE|CD}-NNN.';

INSERT INTO schema_migrations (version) VALUES ('006_knowledge_terms_structured');

COMMIT;
