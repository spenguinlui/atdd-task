-- Test org for smoke tests — isolated from personal/company data
BEGIN;

INSERT INTO organizations (id, name, slug) VALUES
    ('00000000-0000-0000-0000-000000000099', '測試', 'test')
ON CONFLICT DO NOTHING;

INSERT INTO schema_migrations (version) VALUES ('004_add_test_org')
ON CONFLICT DO NOTHING;

COMMIT;
