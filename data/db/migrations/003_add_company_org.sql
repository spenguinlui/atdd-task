-- Phase 6: Add company org for multi-datasource architecture
-- personal org = local DB (side projects)
-- company org = server DB (company projects)

BEGIN;

INSERT INTO organizations (id, name, slug) VALUES
    ('00000000-0000-0000-0000-000000000002', '公司', 'company')
ON CONFLICT DO NOTHING;

INSERT INTO schema_migrations (version) VALUES ('003_add_company_org')
ON CONFLICT DO NOTHING;

COMMIT;
