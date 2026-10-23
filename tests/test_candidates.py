from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from auto_postul.db.models import Candidate
from auto_postul.db.seed import get_or_create_candidate
from auto_postul.db.session import session_scope


def test_create_and_select_candidate(client: TestClient, csrf: str) -> None:
    response = client.post(
        "/candidates",
        data={"_csrf": csrf, "full_name": "QA Candidate", "headline": "Backend"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    with session_scope() as session:
        active = get_or_create_candidate(session)
        assert active.full_name == "QA Candidate"
        rows = session.scalars(select(Candidate)).all()
        assert len(rows) >= 2

    page = client.get("/candidates")
    assert page.status_code == 200
    assert "QA Candidate" in page.text
