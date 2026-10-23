from __future__ import annotations

from sqlalchemy import delete

from auto_postul.application.queue import claim_next, enqueue, fail, finish
from auto_postul.db.models import AutomationRun
from auto_postul.db.session import session_scope
from auto_postul.domain.enums import TaskKind


def test_queue_lifecycle() -> None:
    with session_scope() as session:
        session.execute(delete(AutomationRun))
        run = enqueue(session, TaskKind.SCAN, {"origen": "test"})
        run_id = run.id

    with session_scope() as session:
        claimed = claim_next(session)
        assert claimed is not None
        assert claimed.id == run_id
        assert claimed.status == "running"

    with session_scope() as session:
        current = session.get(AutomationRun, run_id)
        assert current is not None
        finish(session, current, result={"ok": True})

    with session_scope() as session:
        current = session.get(AutomationRun, run_id)
        assert current is not None
        assert current.status == "done"
        assert current.result == {"ok": True}


def test_queue_fail() -> None:
    with session_scope() as session:
        session.execute(delete(AutomationRun))
        run = enqueue(session, TaskKind.PREPARE, {})
        run_id = run.id

    with session_scope() as session:
        current = claim_next(session)
        assert current is not None
        fail(session, current, "boom")

    with session_scope() as session:
        current = session.get(AutomationRun, run_id)
        assert current is not None
        assert current.status == "failed"
        assert current.error == "boom"
