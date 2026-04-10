"""API endpoint integration tests — verify routers call services correctly."""

from __future__ import annotations


class TestTaskEndpoints:
    def test_list_tasks(self, client):
        resp = client.get("/api/v1/tasks")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data

    def test_list_tasks_with_filters(self, client):
        resp = client.get("/api/v1/tasks?limit=3&offset=0")
        assert resp.status_code == 200
        assert len(resp.json()["items"]) <= 3

    def test_get_task_not_found(self, client):
        resp = client.get("/api/v1/tasks/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404

    def test_get_task_history(self, client):
        # Get a real task first
        tasks = client.get("/api/v1/tasks?limit=1").json()
        if tasks["items"]:
            task_id = tasks["items"][0]["id"]
            resp = client.get(f"/api/v1/tasks/{task_id}/history")
            assert resp.status_code == 200
            assert isinstance(resp.json(), list)


class TestDomainEndpoints:
    def test_list_domains(self, client):
        resp = client.get("/api/v1/domains")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_domain_not_found(self, client):
        resp = client.get("/api/v1/domains/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404

    def test_list_couplings(self, client):
        resp = client.get("/api/v1/domains/couplings/list")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestKnowledgeEndpoints:
    def test_list_entries(self, client):
        resp = client.get("/api/v1/knowledge/entries")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data

    def test_list_entries_with_filter(self, client):
        resp = client.get("/api/v1/knowledge/entries?limit=3")
        assert resp.status_code == 200
        assert len(resp.json()["items"]) <= 3

    def test_get_entry_not_found(self, client):
        resp = client.get("/api/v1/knowledge/entries/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404

    def test_list_terms(self, client):
        resp = client.get("/api/v1/knowledge/terms")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestReportEndpoints:
    def test_list_reports(self, client):
        resp = client.get("/api/v1/reports")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_report_not_found(self, client):
        resp = client.get("/api/v1/reports/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404


class TestDashboardPages:
    def test_overview(self, client):
        resp = client.get("/dashboard/")
        assert resp.status_code == 200
        assert "ATDD Dashboard" in resp.text

    def test_overview_with_period(self, client):
        resp = client.get("/dashboard/?period=7d")
        assert resp.status_code == 200

    def test_task_board(self, client):
        resp = client.get("/dashboard/tasks")
        assert resp.status_code == 200
        assert "Task Board" in resp.text

    def test_domain_health(self, client):
        resp = client.get("/dashboard/domains")
        assert resp.status_code == 200
        assert "Domain Health" in resp.text

    def test_causation(self, client):
        resp = client.get("/dashboard/causation")
        assert resp.status_code == 200

    def test_knowledge(self, client):
        resp = client.get("/dashboard/knowledge")
        assert resp.status_code == 200
        assert "Knowledge" in resp.text

    def test_knowledge_with_filters(self, client):
        resp = client.get("/dashboard/knowledge?file_type=strategic")
        assert resp.status_code == 200

    def test_health_endpoint(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
