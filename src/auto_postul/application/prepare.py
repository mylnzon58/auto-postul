"""Casos de uso: preparar y enviar una postulación Easy Apply."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from auto_postul.config import Settings
from auto_postul.db.base import utcnow
from auto_postul.db.models import (
    AnswerBank,
    Application,
    ApplicationEvent,
    ApplicationField,
    Artifact,
    Candidate,
    CandidateDocument,
    JobPosting,
    JobScore,
)
from auto_postul.domain.enums import ApplicationStatus
from auto_postul.domain.schemas import PrepareResult, SubmitResult
from auto_postul.infrastructure.linkedin_apply import (
    ApplyContext,
    file_sha256,
)
from auto_postul.infrastructure.linkedin_apply import (
    prepare_application as browser_prepare,
)
from auto_postul.infrastructure.linkedin_apply import (
    submit_application as browser_submit,
)

logger = logging.getLogger(__name__)


class ApplicationError(RuntimeError):
    """Error de negocio al preparar o enviar una postulación."""


def _candidate_dict(candidate: Candidate) -> dict[str, str]:
    parts = candidate.full_name.split()
    return {
        "full_name": candidate.full_name,
        "first_name": parts[0] if parts else "",
        "last_name": " ".join(parts[1:]) if len(parts) > 1 else "",
        "email": candidate.email,
        "phone": candidate.phone,
        "location": candidate.location,
        "linkedin_url": candidate.linkedin_url,
        "github_url": candidate.github_url,
        "portfolio_url": candidate.portfolio_url,
        "years_experience": str(int(candidate.years_experience or 0)),
        "english_level": candidate.english_level,
    }


def _answers(session: Session, candidate_id: str) -> dict[str, str]:
    rows = session.scalars(
        select(AnswerBank).where(
            AnswerBank.candidate_id == candidate_id,
            AnswerBank.verified.is_(True),
        )
    ).all()
    return {row.key: row.answer for row in rows}


def _primary_resume(session: Session, candidate_id: str) -> CandidateDocument | None:
    return session.scalars(
        select(CandidateDocument)
        .where(
            CandidateDocument.candidate_id == candidate_id,
            CandidateDocument.is_primary.is_(True),
        )
        .order_by(CandidateDocument.created_at.desc())
    ).first()


def _latest_score(session: Session, candidate_id: str, job_id: str) -> JobScore | None:
    return session.scalars(
        select(JobScore)
        .where(JobScore.candidate_id == candidate_id, JobScore.job_id == job_id)
        .order_by(JobScore.created_at.desc())
    ).first()


def _event(session: Session, application_id: str, event_type: str, message: str) -> None:
    session.add(
        ApplicationEvent(
            application_id=application_id,
            event_type=event_type,
            message=message,
        )
    )


def _artifact(
    session: Session,
    application_id: str,
    path: str,
    kind: str = "screenshot",
) -> None:
    file_path = Path(path)
    digest = file_sha256(file_path) if file_path.exists() else ""
    session.add(
        Artifact(
            application_id=application_id,
            kind=kind,
            path=path,
            sha256=digest,
        )
    )


async def prepare(
    session: Session,
    settings: Settings,
    job_id: str,
    *,
    candidate_id: str | None = None,
) -> tuple[Application, PrepareResult]:
    """Prepara el formulario y lo deja en revisión humana."""
    job = session.get(JobPosting, job_id)
    if job is None:
        raise ApplicationError("La oferta no existe.")
    candidate = (
        session.get(Candidate, candidate_id)
        if candidate_id
        else session.scalars(select(Candidate).order_by(Candidate.created_at)).first()
    )
    if candidate is None:
        raise ApplicationError("No hay perfil de candidato.")
    if job.apply_type != "easy_apply":
        raise ApplicationError(
            "Esta oferta no es Easy Apply. El envío automático está deshabilitado."
        )
    if job.apply_type in ("applied", "closed"):
        raise ApplicationError("La oferta ya fue aplicada o está cerrada.")

    resume = _primary_resume(session, candidate.id)
    if resume is None or not Path(resume.stored_path).exists():
        raise ApplicationError("No hay un CV principal disponible. Importá tu CV primero.")

    application = session.scalars(
        select(Application).where(
            Application.candidate_id == candidate.id,
            Application.job_id == job.id,
        )
    ).first()
    if application is None:
        application = Application(candidate_id=candidate.id, job_id=job.id)
        session.add(application)
        session.flush()
    if application.status == ApplicationStatus.SUBMITTED.value:
        raise ApplicationError("Esta oferta ya fue enviada.")
    if application.status == ApplicationStatus.SUBMISSION_UNKNOWN.value:
        raise ApplicationError(
            "El envío anterior quedó en estado desconocido. Revisá LinkedIn antes de reintentar."
        )

    score = _latest_score(session, candidate.id, job.id)
    application.status = ApplicationStatus.PREPARING.value
    application.score_id = score.id if score else None
    application.resume_document_id = resume.id
    application.error = ""
    session.execute(
        delete(ApplicationField).where(ApplicationField.application_id == application.id)
    )
    _event(session, application.id, "status_changed", "Preparando formulario Easy Apply.")
    session.commit()

    context = ApplyContext(
        application_id=application.id,
        job_url=job.url,
        candidate=_candidate_dict(candidate),
        answers=_answers(session, candidate.id),
        resume_path=Path(resume.stored_path),
        settings=settings,
    )
    result = await browser_prepare(context)

    application.status = _map_status(result.status)
    application.prepared_at = (
        utcnow() if result.status in ("ready_for_review", "needs_input") else None
    )
    application.error = result.message if result.status in ("failed", "needs_input") else ""
    application.browser_state = result.browser_state
    for field in result.fields:
        session.add(
            ApplicationField(
                application_id=application.id,
                field_key=field.key,
                label=field.label,
                field_type=field.field_type,
                value=field.value,
                source=field.source,
                confidence=field.confidence,
                required=field.required,
                status=field.status,
                options=field.options,
                step=field.step,
            )
        )
    if result.screenshot:
        _artifact(session, application.id, result.screenshot)
    _event(session, application.id, "status_changed", result.message or result.status)
    if result.status == "needs_input":
        _event(
            session,
            application.id,
            "field_unknown",
            "Hay campos obligatorios sin respuesta verificada. Completá el banco de respuestas.",
        )
    session.commit()
    return application, result


def _map_status(status: str) -> str:
    mapping = {
        "ready_for_review": ApplicationStatus.READY_FOR_REVIEW.value,
        "needs_input": ApplicationStatus.NEEDS_INPUT.value,
        "failed": ApplicationStatus.FAILED.value,
        "dry_run": ApplicationStatus.READY_FOR_REVIEW.value,
    }
    return mapping.get(status, ApplicationStatus.FAILED.value)


async def submit(
    session: Session,
    settings: Settings,
    application_id: str,
    *,
    confirmation: str,
) -> tuple[Application, SubmitResult]:
    """Envía solo con confirmación explícita y modo live."""
    application = session.get(Application, application_id)
    if application is None:
        raise ApplicationError("La postulación no existe.")
    if application.status == ApplicationStatus.SUBMITTED.value:
        raise ApplicationError("La postulación ya fue enviada.")
    if application.status != ApplicationStatus.READY_FOR_REVIEW.value:
        raise ApplicationError("La postulación todavía no está lista para revisión.")
    if confirmation.strip().upper() != "ENVIAR":
        raise ApplicationError("Escribí ENVIAR para confirmar la postulación.")

    today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    sent_today = session.scalar(
        select(func.count(Application.id)).where(
            Application.candidate_id == application.candidate_id,
            Application.submitted_at.is_not(None),
            Application.submitted_at >= today,
        )
    )
    if int(sent_today or 0) >= settings.daily_apply_limit:
        raise ApplicationError(
            f"Límite diario de postulaciones alcanzado ({settings.daily_apply_limit})."
        )

    application.status = ApplicationStatus.SUBMITTING.value
    application.confirmation_text = confirmation
    _event(session, application.id, "status_changed", "Envío confirmado por el usuario.")
    session.commit()

    result = await browser_submit(application.id, settings)
    if result.status == "submitted":
        application.status = ApplicationStatus.SUBMITTED.value
        application.submitted_at = utcnow()
        application.error = ""
        _event(session, application.id, "submitted", result.message)
    elif result.status == "submission_unknown":
        application.status = ApplicationStatus.SUBMISSION_UNKNOWN.value
        application.error = result.message
        _event(session, application.id, "submission_unknown", result.message)
    elif result.status == "dry_run":
        application.status = ApplicationStatus.READY_FOR_REVIEW.value
        _event(session, application.id, "note", result.message)
    else:
        application.status = ApplicationStatus.FAILED.value
        application.error = result.message
        _event(session, application.id, "error", result.message)
    if result.screenshot:
        _artifact(session, application.id, result.screenshot)
    application.browser_state = result.browser_state
    session.commit()
    return application, result


def serialize_application(application: Application) -> dict[str, Any]:
    return {
        "id": application.id,
        "status": application.status,
        "job_id": application.job_id,
        "mode": application.mode,
        "prepared_at": application.prepared_at.isoformat() if application.prepared_at else None,
        "submitted_at": application.submitted_at.isoformat() if application.submitted_at else None,
        "error": application.error,
    }
