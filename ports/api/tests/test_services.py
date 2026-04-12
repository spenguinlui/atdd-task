"""Service layer unit tests — verify services query DB correctly."""

from __future__ import annotations

from services import task_service, domain_service, knowledge_service, overview_service, report_service


class TestTaskService:
    def test_list_projects_returns_list(self):
        projects = task_service.list_projects("00000000-0000-0000-0000-000000000001")
        assert isinstance(projects, list)
        assert all(isinstance(p, str) for p in projects)

    def test_list_tasks_returns_paginated(self):
        result = task_service.list_tasks("00000000-0000-0000-0000-000000000001", limit=5)
        assert "items" in result
        assert "total" in result
        assert len(result["items"]) <= 5

    def test_list_tasks_filter_by_project(self):
        projects = task_service.list_projects("00000000-0000-0000-0000-000000000001")
        if projects:
            result = task_service.list_tasks(
                "00000000-0000-0000-0000-000000000001",
                project=projects[0], limit=10,
            )
            for item in result["items"]:
                assert item["project"] == projects[0]

    def test_list_tasks_for_board(self):
        tasks = task_service.list_tasks_for_board("00000000-0000-0000-0000-000000000001")
        assert isinstance(tasks, list)
        for t in tasks:
            assert "id" in t
            assert "status" in t
            assert "type" in t

    def test_list_fix_tasks_with_causation(self):
        tasks = task_service.list_fix_tasks_with_causation("00000000-0000-0000-0000-000000000001")
        assert isinstance(tasks, list)
        for t in tasks:
            assert t["type"] == "fix"
            assert t["causation"] is not None

    def test_get_task_not_found(self):
        result = task_service.get_task("00000000-0000-0000-0000-000000000000")
        assert result is None

    def test_list_task_history(self):
        # Get a real task ID first
        result = task_service.list_tasks("00000000-0000-0000-0000-000000000001", limit=1)
        if result["items"]:
            task_id = str(result["items"][0]["id"])
            history = task_service.list_task_history(task_id)
            assert isinstance(history, list)


class TestDomainService:
    def test_list_domains(self):
        domains = domain_service.list_domains("00000000-0000-0000-0000-000000000001")
        assert isinstance(domains, list)

    def test_list_sidebar_domains_grouped(self):
        grouped = domain_service.list_sidebar_domains("00000000-0000-0000-0000-000000000001")
        assert isinstance(grouped, dict)
        for project, doms in grouped.items():
            assert isinstance(project, str)
            assert isinstance(doms, list)
            for d in doms:
                assert "name" in d
                assert "project" in d

    def test_get_domain_by_name(self):
        domains = domain_service.list_domains("00000000-0000-0000-0000-000000000001")
        if domains:
            d = domains[0]
            found = domain_service.get_domain_by_name(
                "00000000-0000-0000-0000-000000000001", d["name"], d["project"],
            )
            assert found is not None
            assert found["name"] == d["name"]

    def test_get_domain_by_name_not_found(self):
        result = domain_service.get_domain_by_name(
            "00000000-0000-0000-0000-000000000001", "nonexistent_domain_xyz",
        )
        assert result is None

    def test_list_couplings(self):
        couplings = domain_service.list_couplings("00000000-0000-0000-0000-000000000001")
        assert isinstance(couplings, list)

    def test_get_domain_knowledge_stats(self):
        domains = domain_service.list_domains("00000000-0000-0000-0000-000000000001")
        if domains:
            stats = domain_service.get_domain_knowledge_stats(
                "00000000-0000-0000-0000-000000000001", domains[0]["name"],
            )
            assert isinstance(stats, dict)


class TestKnowledgeService:
    def test_list_entries_paginated(self):
        result = knowledge_service.list_entries("00000000-0000-0000-0000-000000000001", limit=5)
        assert "items" in result
        assert "total" in result
        assert len(result["items"]) <= 5

    def test_get_type_stats(self):
        stats = knowledge_service.get_type_stats("00000000-0000-0000-0000-000000000001")
        assert isinstance(stats, list)
        for s in stats:
            assert "file_type" in s
            assert "cnt" in s

    def test_list_entries_grouped(self):
        grouped = knowledge_service.list_entries_grouped("00000000-0000-0000-0000-000000000001")
        assert isinstance(grouped, dict)
        for domain_name, entries in grouped.items():
            assert isinstance(entries, list)
            for e in entries:
                assert "id" in e
                assert "content" in e

    def test_list_all_domains(self):
        domains = knowledge_service.list_all_domains("00000000-0000-0000-0000-000000000001")
        assert isinstance(domains, list)
        assert all(isinstance(d, str) for d in domains)

    def test_list_terms(self):
        terms = knowledge_service.list_terms("00000000-0000-0000-0000-000000000001")
        assert isinstance(terms, list)
        for t in terms:
            assert "english_term" in t
            assert "chinese_term" in t

    def test_get_entry_not_found(self):
        result = knowledge_service.get_entry("00000000-0000-0000-0000-000000000000")
        assert result is None


class TestOverviewService:
    def test_type_status_aggregation(self):
        result = overview_service.get_type_status_aggregation("00000000-0000-0000-0000-000000000001")
        assert isinstance(result, list)
        for r in result:
            assert "type" in r
            assert "status" in r
            assert "cnt" in r

    def test_weekly_trends(self):
        result = overview_service.get_weekly_trends("00000000-0000-0000-0000-000000000001")
        assert isinstance(result, list)
        for r in result:
            assert "week" in r
            assert "created" in r
            assert "completed" in r

    def test_cost_by_type(self):
        result = overview_service.get_cost_by_type("00000000-0000-0000-0000-000000000001")
        assert isinstance(result, list)


class TestReportService:
    def test_list_reports(self):
        reports = report_service.list_reports("00000000-0000-0000-0000-000000000001")
        assert isinstance(reports, list)

    def test_get_report_not_found(self):
        result = report_service.get_report("00000000-0000-0000-0000-000000000000")
        assert result is None
