"""
Pruebas de uniteval.reports y sus endpoints.
"""

from pathlib import Path

from fastapi.testclient import TestClient

from uniteval import reports
from uniteval.app import app

def test_reports_save_update_and_list(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(reports, "REPORTS_DIR", tmp_path / "reports")
    assert reports.list_reports() == []

    first = reports.save_report({"project_path": "a", "summary": {"average": 4}, "analyses": {"t": 1}})
    assert reports.is_valid_id(first["id"])
    assert reports.get_report(first["id"])["analyses"] == {"t": 1}

    updated = reports.save_report({"project_path": "a", "analyses": {"t": 2}}, first["id"])
    assert updated["created_at"] == first["created_at"]
    assert len(reports.list_reports()) == 1

    listed = reports.list_reports()[0]
    assert listed["id"] == first["id"]
    assert "analyses" not in listed


def test_reports_list_orders_recent_first_and_skips_corrupt_files(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(reports, "REPORTS_DIR", tmp_path)
    (tmp_path / "20250101-000000-aaaaaa.json").write_text('{"id": "viejo", "created_at": "2025-01-01"}', encoding="utf-8")
    (tmp_path / "20260101-000000-bbbbbb.json").write_text('{"id": "nuevo", "created_at": "2026-01-01"}', encoding="utf-8")
    (tmp_path / "20260101-000000-cccccc.json").write_text("{roto", encoding="utf-8")

    assert [r["id"] for r in reports.list_reports()] == ["nuevo", "viejo"]


def test_reports_endpoints(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(reports, "REPORTS_DIR", tmp_path / "reports")
    client = TestClient(app)

    assert client.get("/api/reports").json() == []
    saved = client.post("/api/reports", json={
        "project_path": "p", "model": "laguna", "summary": {"analyzed": 1}, "analyses": {"t": {"quality": "alta"}},
    }).json()

    assert client.get(f"/api/reports/{saved['id']}").json()["analyses"]["t"]["quality"] == "alta"
    assert len(client.get("/api/reports").json()) == 1
    assert client.get("/api/reports/20260101-000000-abcdef").status_code == 404
    assert client.get("/api/reports/no-valido").status_code == 404
    assert client.post("/api/reports", json={"id": "../config"}).status_code == 400
    assert not (tmp_path / "config.json").exists()
