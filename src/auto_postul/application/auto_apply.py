"""Auto-postulación controlada para ofertas remotas de alta afinidad."""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from auto_postul.application.prepare import ApplicationError, prepare, submit
from auto_postul.config import Settings
from auto_postul.db.models import (
    Application,
    Candidate,
    JobPosting,
    JobScore,
    Setting,
)
from auto_postul.db.seed import get_or_create_candidate
from auto_postul.domain.enums import ApplicationStatus

AUTO_SETTING_KEY = "auto_apply"


@dataclass(slots=True)
class AutoSettings:
    enabled: bool = False
    min_score: int = 80
    daily_limit: int = 5
    delay_min_seconds: int = 45
    delay_max_seconds: int = 120
    remote_only: bool = True


def get_auto_settings(session: Session) -> AutoSettings:
    """Lee la configuración de auto-postulación desde la base local."""
    row = session.get(Setting, AUTO_SETTING_KEY)
    value: dict[str, Any] = row.value if row is not None and isinstance(row.value, dict) else {}
    return AutoSettings(
        enabled=bool(value.get("enabled", False)),
        min_score=max(0, min(100, int(value.get("min_score", 80)))),
        daily_limit=max(0, min(50, int(value.get("daily_limit", 5)))),
        delay_min_seconds=max(5, min(3600, int(value.get("delay_min_seconds", 45)))),
        delay_max_seconds=max(5, min(7200, int(value.get("delay_max_seconds", 120)))),
        remote_only=bool(value.get("remote_only", True)),
    )


def save_auto_settings(session: Session, values: dict[str, Any]) -> AutoSettings:
    """Valida y persiste la configuración de auto-postulación."""
    current = get_auto_settings(session)
    min_score = max(0, min(100, int(values.get("min_score", current.min_score))))
    daily_limit = max(0, min(50, int(values.get("daily_limit", current.daily_limit))))
    delay_min = max(5, min(3600, int(values.get("delay_min_seconds", current.delay_min_seconds))))
    delay_max = max(
        delay_min, min(7200, int(values.get("delay_max_seconds", current.delay_max_seconds)))
    )
    payload = {
        "enabled": bool(values.get("enabled", current.enabled)),
        "min_score": min_score,
        "daily_limit": daily_limit,
        "delay_min_seconds": delay_min,
        "delay_max_seconds": delay_max,
        "remote_only": bool(values.get("remote_only", current.remote_only)),
    }
    row = session.get(Setting, AUTO_SETTING_KEY)
    if row is None:
        session.add(Setting(key=AUTO_SETTING_KEY, value=payload))
    else:
        row.value = payload
    session.flush()
    return AutoSettings(
        enabled=bool(payload["enabled"]),
        min_score=int(payload["min_score"]),
        daily_limit=int(payload["daily_limit"]),
        delay_min_seconds=int(payload["delay_min_seconds"]),
        delay_max_seconds=int(payload["delay_max_seconds"]),
        remote_only=bool(payload["remote_only"]),
    )


def submitted_today(session: Session, candidate_id: str) -> int:
    today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    value = session.scalar(
        select(func.count(Application.id)).where(
            Application.candidate_id == candidate_id,
            Application.submitted_at.is_not(None),
            Application.submitted_at >= today,
        )
    )
    return int(value or 0)


def _latest_scores(session: Session, candidate_id: str) -> dict[str, JobScore]:
    rows = session.scalars(
        select(JobScore)
        .where(JobScore.candidate_id == candidate_id)
        .order_by(JobScore.created_at.desc())
    ).all()
    result: dict[str, JobScore] = {}
    for row in rows:
        result.setdefault(row.job_id, row)
    return result


def eligible_jobs(
    session: Session, candidate: Candidate, config: AutoSettings
) -> list[tuple[JobPosting, JobScore]]:
    """Ofertas Easy Apply, remotas, con score suficiente y sin envío previo."""
    scores = _latest_scores(session, candidate.id)
    applications = {
        row.job_id: row
        for row in session.scalars(
            select(Application).where(Application.candidate_id == candidate.id)
        ).all()
    }
    jobs = session.scalars(select(JobPosting).where(JobPosting.apply_type == "easy_apply")).all()
    result: list[tuple[JobPosting, JobScore]] = []
    for job in jobs:
        score = scores.get(job.id)
        if score is None or score.total < config.min_score:
            continue
        if config.remote_only and job.work_mode != "remote":
            continue
        application = applications.get(job.id)
        if application is not None and application.status in (
            ApplicationStatus.SUBMITTED.value,
            ApplicationStatus.SUBMISSION_UNKNOWN.value,
        ):
            continue
        result.append((job, score))
    # Mayor afinidad primero; un pequeño jitter evita un orden perfectamente idéntico.
    result.sort(key=lambda pair: (pair[1].total, random.random()), reverse=True)
    return result


async def run_auto_apply(
    session: Session,
    settings: Settings,
    *,
    max_jobs: int | None = None,
) -> dict[str, Any]:
    """Prepara y envía ofertas elegibles, con pausas aleatorias y topes."""
    config = get_auto_settings(session)
    if not config.enabled:
        raise ApplicationError("La auto-postulación está deshabilitada en Ajustes.")
    if settings.apply_dry_run or not settings.apply_live_submit:
        raise ApplicationError(
            "La auto-postulación real requiere APPLY_DRY_RUN=false y APPLY_LIVE_SUBMIT=true."
        )

    candidate = get_or_create_candidate(session)
    already_sent = submitted_today(session, candidate.id)
    remaining = max(0, config.daily_limit - already_sent)
    if max_jobs is not None:
        remaining = min(remaining, max(0, max_jobs))
    if remaining <= 0:
        return {
            "sent": 0,
            "skipped": 0,
            "errors": [],
            "message": "Límite diario de auto-postulación alcanzado.",
        }

    jobs = eligible_jobs(session, candidate, config)
    sent = 0
    skipped = 0
    errors: list[str] = []
    stopped_reason = ""

    for job, _score in jobs:
        if sent >= remaining:
            break
        if sent > 0 or skipped > 0:
            delay = random.uniform(config.delay_min_seconds, config.delay_max_seconds)
            await asyncio.sleep(delay)
        else:
            await asyncio.sleep(random.uniform(3, 8))

        try:
            application, prepare_result = await prepare(session, settings, job.id)
        except ApplicationError as exc:
            skipped += 1
            errors.append(f"{job.title}: {exc}")
            continue

        if prepare_result.status != "ready_for_review":
            skipped += 1
            errors.append(f"{job.title}: preparación {prepare_result.status}")
            continue

        try:
            application, submit_result = await submit(
                session,
                settings,
                application.id,
                confirmation="ENVIAR",
            )
        except ApplicationError as exc:
            skipped += 1
            errors.append(f"{job.title}: {exc}")
            continue

        if submit_result.status == "submitted":
            sent += 1
        elif submit_result.status == "submission_unknown":
            errors.append(f"{job.title}: envío ambiguo, auto-postulación detenida.")
            stopped_reason = "submission_unknown"
            break
        else:
            skipped += 1
            errors.append(f"{job.title}: {submit_result.message}")

    message = f"Auto-postulación: {sent} enviadas, {skipped} omitidas."
    if stopped_reason == "submission_unknown":
        message += " Se detuvo por un envío de resultado desconocido."
    return {
        "sent": sent,
        "skipped": skipped,
        "errors": errors,
        "stopped_reason": stopped_reason,
        "remaining": max(0, remaining - sent),
        "message": message,
    }
