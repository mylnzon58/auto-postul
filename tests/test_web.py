from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from auto_postul.db.models import AutomationRun, SearchProfile
from auto_postul.db.session import session_scope
from auto_postul.domain.enums import TaskKind


def test_health(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["dry_run"] is True


def test_main_pages_render(client: TestClient) -> None:
    for path in ("/", "/jobs", "/profile", "/searches", "/activity", "/settings", "/applications"):
        response = client.get(path)
        assert response.status_code == 200, path
        assert "AutoPostul" in response.text


def test_create_search(client: TestClient, csrf: str) -> None:
    with session_scope() as session:
        session.execute(delete(SearchProfile).where(SearchProfile.name == "Prueba QA"))

    response = client.post(
        "/searches",
        data={
            "_csrf": csrf,
            "name": "Prueba QA",
            "keywords": "Python backend",
            "location": "Argentina",
            "work_type": "remote",
            "date_posted": "past_week",
            "min_score": "70",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    with session_scope() as session:
        row = session.scalars(
            select(SearchProfile).where(SearchProfile.name == "Prueba QA")
        ).first()
        assert row is not None
        assert row.min_score == 70


def test_scan_enqueues_task(client: TestClient, csrf: str) -> None:
    with session_scope() as session:
        session.execute(delete(AutomationRun))

    response = client.post(
        "/actions/scan",
        data={"_csrf": csrf},
        follow_redirects=False,
    )

    assert response.status_code == 303
    with session_scope() as session:
        run = session.scalars(select(AutomationRun)).first()
        assert run is not None
        assert run.kind == TaskKind.SCAN.value
        assert run.status == "queued"


def test_post_without_csrf_is_rejected(client: TestClient) -> None:
    response = client.post("/actions/scan", data={})

    assert response.status_code == 403
