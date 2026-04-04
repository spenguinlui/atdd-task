-- Phase 2: Initial Schema
-- Multi-org aware from day one (org_id on all tenant tables)

BEGIN;

-- Track applied migrations
CREATE TABLE IF NOT EXISTS schema_migrations (
    version  TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Extensions
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================
-- Organizations
-- ============================================================
CREATE TABLE organizations (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name       TEXT NOT NULL,
    slug       TEXT NOT NULL UNIQUE,
    settings   JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Seed a default org for bootstrapping
INSERT INTO organizations (id, name, slug) VALUES
    ('00000000-0000-0000-0000-000000000001', '個人', 'personal');

-- ============================================================
-- Tasks
-- ============================================================
CREATE TYPE task_type   AS ENUM ('feature', 'fix', 'refactor', 'test', 'epic');
CREATE TYPE task_status AS ENUM (
    'pending_spec', 'specifying', 'pending_dev', 'developing',
    'pending_review', 'reviewing', 'gate',
    'deployed', 'verified', 'escaped',
    'completed', 'aborted'
);

CREATE TABLE tasks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES organizations(id),
    project         TEXT NOT NULL,
    type            task_type NOT NULL,
    status          task_status NOT NULL DEFAULT 'pending_spec',
    phase           TEXT,
    domain          TEXT,
    related_domains TEXT[],
    description     TEXT,
    requirement     TEXT,
    causation       JSONB,
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_tasks_org_project ON tasks (org_id, project);
CREATE INDEX idx_tasks_status      ON tasks (status);
CREATE INDEX idx_tasks_domain      ON tasks (domain);
CREATE INDEX idx_tasks_created     ON tasks (created_at DESC);

-- ============================================================
-- Task History (event log)
-- ============================================================
CREATE TABLE task_history (
    id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id   UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    phase     TEXT,
    status    TEXT,
    agent     TEXT,
    note      TEXT,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_task_history_task ON task_history (task_id, timestamp);

-- ============================================================
-- Task Metrics (per-agent resource usage)
-- ============================================================
CREATE TABLE task_metrics (
    id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id   UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    agent     TEXT NOT NULL,
    tool_uses INT,
    tokens    INT,
    duration  INT,  -- seconds
    timestamp TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_task_metrics_task ON task_metrics (task_id);

-- ============================================================
-- Domain Health
-- ============================================================
CREATE TYPE domain_status AS ENUM ('healthy', 'degraded', 'critical');

CREATE TABLE domains (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id             UUID NOT NULL REFERENCES organizations(id),
    project            TEXT NOT NULL,
    name               TEXT NOT NULL,
    health_score       NUMERIC(5,2),
    status             domain_status,
    fix_rate           NUMERIC(5,4),
    coupling_rate      NUMERIC(5,4),
    change_frequency   NUMERIC(5,4),
    knowledge_coverage NUMERIC(5,4),
    escape_rate        NUMERIC(5,4),
    calculated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (org_id, project, name)
);

CREATE INDEX idx_domains_org_project ON domains (org_id, project);

-- ============================================================
-- Domain Couplings
-- ============================================================
CREATE TABLE domain_couplings (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id              UUID NOT NULL REFERENCES organizations(id),
    project             TEXT NOT NULL,
    domain_a            TEXT NOT NULL,
    domain_b            TEXT NOT NULL,
    co_occurrence_count INT NOT NULL DEFAULT 0,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (org_id, project, domain_a, domain_b)
);

-- ============================================================
-- Knowledge Entries (段落級)
-- ============================================================
CREATE TABLE knowledge_entries (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id     UUID NOT NULL REFERENCES organizations(id),
    project    TEXT NOT NULL,
    domain     TEXT,
    file_type  TEXT,       -- 'strategic', 'tactical', 'business-rules', 'domain-map'
    section    TEXT,
    content    TEXT NOT NULL,
    version    INT NOT NULL DEFAULT 1,
    updated_by TEXT,       -- 'slack:U123' or 'claude:session_xxx'
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_knowledge_org_project ON knowledge_entries (org_id, project);
CREATE INDEX idx_knowledge_domain      ON knowledge_entries (domain);

-- ============================================================
-- Knowledge Terms (UL 術語)
-- ============================================================
CREATE TABLE knowledge_terms (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id       UUID NOT NULL REFERENCES organizations(id),
    project      TEXT NOT NULL,
    domain       TEXT,
    english_term TEXT NOT NULL,
    chinese_term TEXT NOT NULL,
    context      TEXT,
    source       TEXT,      -- 'ul.md', 'slack', 'code'
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (org_id, project, english_term)
);

-- ============================================================
-- Reports
-- ============================================================
CREATE TABLE reports (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id     UUID NOT NULL REFERENCES organizations(id),
    project    TEXT NOT NULL,
    type       TEXT NOT NULL,  -- 'weekly', 'monthly', 'domain-health', 'causation'
    period     TEXT,           -- '2026-W14', '2026-03'
    data       JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_reports_org_project ON reports (org_id, project);
CREATE INDEX idx_reports_type_period ON reports (type, period);

-- ============================================================
-- Updated_at trigger
-- ============================================================
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_organizations_updated BEFORE UPDATE ON organizations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_tasks_updated BEFORE UPDATE ON tasks
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_domains_updated BEFORE UPDATE ON domains
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_knowledge_entries_updated BEFORE UPDATE ON knowledge_entries
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_knowledge_terms_updated BEFORE UPDATE ON knowledge_terms
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- Record this migration
INSERT INTO schema_migrations (version) VALUES ('001_initial');

COMMIT;
