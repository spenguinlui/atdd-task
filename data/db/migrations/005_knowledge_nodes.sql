-- 005 Knowledge Nodes — 結構化知識層
-- 策略：additive，不動 knowledge_entries / knowledge_terms 現有欄位
BEGIN;

-- ============================================================
-- knowledge_nodes：結構化知識節點
-- ============================================================
CREATE TABLE knowledge_nodes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES organizations(id),
    project         TEXT NOT NULL,
    domain          TEXT NOT NULL,

    layer           TEXT NOT NULL,
    node_type       TEXT NOT NULL,
    slug            TEXT NOT NULL,
    title           TEXT NOT NULL,
    summary         TEXT NOT NULL,

    attrs           JSONB NOT NULL DEFAULT '{}'::jsonb,
    body_md         TEXT,

    source_task_id  UUID REFERENCES tasks(id) ON DELETE SET NULL,
    legacy_entry_id UUID REFERENCES knowledge_entries(id) ON DELETE SET NULL,

    stale           BOOLEAN NOT NULL DEFAULT false,
    version         INT NOT NULL DEFAULT 1,
    updated_by      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (org_id, project, domain, layer, node_type, slug),
    CHECK (layer IN ('strategic', 'tactical', 'rule'))
);

CREATE INDEX idx_knowledge_nodes_project_domain ON knowledge_nodes (org_id, project, domain);
CREATE INDEX idx_knowledge_nodes_type           ON knowledge_nodes (org_id, project, layer, node_type);
CREATE INDEX idx_knowledge_nodes_stale          ON knowledge_nodes (org_id, project) WHERE stale = true;
CREATE INDEX idx_knowledge_nodes_attrs          ON knowledge_nodes USING GIN (attrs);

CREATE TRIGGER trg_knowledge_nodes_updated
    BEFORE UPDATE ON knowledge_nodes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ============================================================
-- knowledge_node_revisions：變更歷史
-- ============================================================
CREATE TABLE knowledge_node_revisions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    node_id         UUID NOT NULL REFERENCES knowledge_nodes(id) ON DELETE CASCADE,
    version         INT NOT NULL,
    attrs           JSONB NOT NULL,
    body_md         TEXT,
    change_reason   TEXT,
    source_task_id  UUID REFERENCES tasks(id) ON DELETE SET NULL,
    changed_by      TEXT,
    changed_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (node_id, version)
);

CREATE INDEX idx_node_revisions_node ON knowledge_node_revisions (node_id, version DESC);

-- ============================================================
-- knowledge_terms：加 node_id 弱關聯
-- ============================================================
ALTER TABLE knowledge_terms
    ADD COLUMN node_id UUID REFERENCES knowledge_nodes(id) ON DELETE SET NULL;

CREATE INDEX idx_knowledge_terms_node ON knowledge_terms (node_id) WHERE node_id IS NOT NULL;

-- ============================================================
-- knowledge_entries：加 migrated 標記
-- ============================================================
ALTER TABLE knowledge_entries
    ADD COLUMN migrated BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN migrated_to_node_id UUID REFERENCES knowledge_nodes(id) ON DELETE SET NULL;

-- Record this migration
INSERT INTO schema_migrations (version) VALUES ('005_knowledge_nodes');

COMMIT;
