"""Cola simple y transaccional sobre SQLite."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from auto_postul.db.base import utcnow
from auto_postul.db.models import AutomationRun, Setting
from auto_postul.domain.enums import TaskKind, TaskStatus


def enqueue(
    session: Session, kind: TaskKind, payload: dict[str, Any] | None = None
) -> AutomationRun:
    """Encola una tarea y devuelve el run creado."""
    run = AutomationRun(kind=kind.value, status=TaskStatus.QUEUED.value, payload=payload or {})
    session.add(run)
    session.flush()
    return run


def find_active(session: Session, kind: TaskKind | None = None) -> AutomationRun | None:
    stmt = select(AutomationRun).where(
        AutomationRun.status.in_([TaskStatus.QUEUED.value, TaskStatus.RUNNING.value])
    )
    if kind is not None:
        stmt = stmt.where(AutomationRun.kind == kind.value)
    return session.scalars(stmt.order_by(AutomationRun.created_at)).first()


def claim_next(session: Session) -> AutomationRun | None:
    """Reclama la tarea más antigua. Un solo worker evita carreras complejas."""
    run = session.scalars(
        select(AutomationRun)
        .where(AutomationRun.status == TaskStatus.QUEUED.value)
        .order_by(AutomationRun.created_at)
        .limit(1)
    ).first()
    if run is None:
        return None
    run.status = TaskStatus.RUNNING.value
    run.started_at = utcnow()
    session.flush()
    return run


def finish(session: Session, run: AutomationRun, *, result: dict[str, Any] | None = None) -> None:
    run.status = TaskStatus.DONE.value
    run.result = result or {}
    run.finished_at = utcnow()
    session.flush()


def fail(session: Session, run: AutomationRun, error: str) -> None:
    run.status = TaskStatus.FAILED.value
    run.error = error[:4000]
    run.finished_at = utcnow()
    session.flush()


def touch_worker(session: Session) -> None:
    """Marca que el worker está vivo para que el panel pueda mostrarlo."""
    payload = {"at": utcnow().isoformat(), "pid": os.getpid()}
    setting = session.get(Setting, "worker_heartbeat")
    if setting is None:
        session.add(Setting(key="worker_heartbeat", value=payload))
    else:
        setting.value = payload


def worker_online(session: Session, *, max_age_seconds: int = 20) -> bool:
    """Devuelve si el worker actualizó su latido recientemente."""
    setting = session.get(Setting, "worker_heartbeat")
    if setting is None:
        return False
    raw = str(setting.value.get("at", ""))
    if not raw:
        return False
    try:
        at = datetime.fromisoformat(raw)
    except ValueError:
        return False
    if at.tzinfo is None:
        at = at.replace(tzinfo=UTC)
    return datetime.now(UTC) - at < timedelta(seconds=max_age_seconds)
