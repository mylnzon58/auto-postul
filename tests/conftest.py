from __future__ import annotations

import os
import tempfile

import pytest

os.environ["APP_DATA_DIR"] = tempfile.mkdtemp(prefix="autopostul-tests-")
os.environ["GEMINI_API_KEY"] = ""
os.environ["APP_PASSWORD"] = ""
os.environ["SESSION_SECRET"] = "test-secret-no-usar-en-produccion"
os.environ["APPLY_DRY_RUN"] = "true"
os.environ["APPLY_LIVE_SUBMIT"] = "false"

from fastapi.testclient import TestClient

from auto_postul.db.seed import seed_defaults
from auto_postul.db.session import init_db, session_scope
from auto_postul.web.app import app


@pytest.fixture(scope="session", autouse=True)
def _prepare_database() -> None:
    init_db()
    with session_scope() as session:
        seed_defaults(session)


@pytest.fixture()
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def csrf(client: TestClient) -> str:
    response = client.get("/")
    assert response.status_code == 200
    marker = 'name="_csrf" value="'
    start = response.text.index(marker) + len(marker)
    end = response.text.index('"', start)
    return response.text[start:end]
