"""Caso de uso: escanear LinkedIn, normalizar ofertas y puntuarlas."""

from __future__ import annotations

import hashlib
import logging
import unicodedata
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from auto_postul.config import Settings
from auto_postul.db.models import (
    Application,
    AutomationRun,
    Candidate,
    CandidatePreference,
    CandidateSkill,
    Company,
    Education,
    JobPosting,
    JobScore,
    JobSkill,
    SearchProfile,
    Skill,
)
from auto_postul.db.seed import get_or_create_candidate
from auto_postul.domain.jobs import detect_apply_type, job_skill_tuples, parse_job_payload
from auto_postul.domain.schemas import ParsedJob
from auto_postul.domain.scoring import CandidateSnapshot, JobSnapshot, score_job
from auto_postul.infrastructure.gemini import GeminiService
from auto_postul.infrastructure.linkedin_mcp import LinkedInMcpClient

logger = logging.getLogger(__name__)


def _today_start() -> datetime:
    now = datetime.now(UTC)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def _count_jobs_today(session: Session) -> int:
    value = session.scalar(
        select(func.count(JobPosting.id)).where(JobPosting.created_at >= _today_start())
    )
    return int(value or 0)


def _normalize_company(name: str) -> str:
    folded = unicodedata.normalize("NFKD", name)
    ascii_name = "".join(char for char in folded if not unicodedata.combining(char))
    return " ".join(ascii_name.casefold().split())


def _get_or_create_company(session: Session, name: str) -> Company | None:
    normalized = _normalize_company(name)
    if not normalized:
        return None
    company = session.scalars(select(Company).where(Company.normalized_name == normalized)).first()
    if company is None:
        company = Company(name=name[:240], normalized_name=normalized)
        session.add(company)
        session.flush()
    return company


def _candidate_snapshot(
    session: Session, candidate: Candidate, search: SearchProfile
) -> CandidateSnapshot:
    rows = session.execute(
        select(Skill.slug, Skill.name)
        .join(CandidateSkill, CandidateSkill.skill_id == Skill.id)
        .where(CandidateSkill.candidate_id == candidate.id)
    ).all()
    skills = {str(slug): str(name) for slug, name in rows}
    pref = session.scalars(
        select(CandidatePreference).where(CandidatePreference.candidate_id == candidate.id)
    ).first()
    education = session.scalars(
        select(Education).where(Education.candidate_id == candidate.id)
    ).all()
    degree_text = " ".join(f"{item.degree} {item.description}" for item in education).casefold()
    has_degree = any(
        marker in degree_text
        for marker in ("ingeniería", "licenciatura", "bachiller", "análisis de sistemas")
    )
    in_progress = any(marker in degree_text for marker in ("en curso", "incompleta", "cursando"))
    return CandidateSnapshot(
        skills=skills,
        target_titles=(list(pref.target_titles) if pref else []) + [search.name, search.keywords],
        tracks=list(search.tracks),
        location=candidate.location,
        work_modes=list(pref.work_modes) if pref else ["remote"],
        years_experience=candidate.years_experience,
        english_level=candidate.english_level,
        has_degree=has_degree,
        degree_in_progress=in_progress,
        headline=candidate.headline,
    )


def _score_and_store(
    session: Session,
    candidate: Candidate,
    search: SearchProfile,
    job: JobPosting,
    parsed: ParsedJob,
) -> JobScore:
    snapshot = _candidate_snapshot(session, candidate, search)
    job_snapshot = JobSnapshot(
        title=job.title,
        company=job.company_name,
        location=job.location,
        work_mode=job.work_mode,
        description=job.description,
        requirements=job.requirements,
        job_family=job.job_family,
        apply_type=job.apply_type,
    )
    result = score_job(snapshot, job_snapshot, job_skill_tuples(parsed), search.min_score)
    score = JobScore(
        job_id=job.id,
        candidate_id=candidate.id,
        search_profile_id=search.id,
        rubric_version=result.rubric_version,
        total=result.total,
        band=result.band,
        components=[component.as_dict() for component in result.components],
        matched_skills=result.matched_skills,
        missing_skills=result.missing_skills,
        risks=result.risks,
        summary=result.summary,
        model="gemini+rubrica" if False else "rubrica-local",
    )
    session.add(score)
    session.flush()
    return score


async def run_scan(
    session: Session,
    settings: Settings,
    *,
    search_profile_id: str | None = None,
    max_jobs: int | None = None,
) -> dict[str, Any]:
    """Escanea búsquedas activas. No crea postulaciones ni envía nada."""
    candidate = get_or_create_candidate(session)
    searches = session.scalars(
        select(SearchProfile).where(
            SearchProfile.candidate_id == candidate.id,
            SearchProfile.enabled.is_(True),
        )
    ).all()
    if search_profile_id:
        searches = [item for item in searches if item.id == search_profile_id]
    if not searches:
        return {"searches": 0, "jobs": 0, "skipped": 0, "message": "No hay búsquedas activas."}

    remaining = max(0, settings.daily_job_detail_limit - _count_jobs_today(session))
    if max_jobs is not None:
        remaining = min(remaining, max(0, max_jobs))
    if remaining <= 0:
        return {
            "searches": 0,
            "jobs": 0,
            "skipped": 0,
            "message": "Límite diario de ofertas alcanzado.",
        }

    gemini = GeminiService(settings)
    new_jobs = 0
    skipped = 0
    skipped_external = 0
    skipped_unknown = 0
    skipped_non_remote = 0
    errors: list[str] = []

    async with LinkedInMcpClient(settings) as mcp:
        try:
            applied_payload = await mcp.get_saved_jobs(stage="applied", max_pages=1)
            applied_ids = {str(item) for item in applied_payload.get("job_ids", [])}
            if mark_existing_applications(session, candidate.id, applied_ids):
                session.commit()
        except Exception as exc:
            errors.append(f"No se pudo sincronizar postulaciones enviadas: {exc}")

        for search in searches:
            try:
                payload = await mcp.search_jobs(
                    search.keywords,
                    location=search.location,
                    max_pages=search.max_pages,
                    date_posted=search.date_posted,
                    work_type=search.work_type,
                    job_type=search.job_type,
                    experience_level=search.experience_level,
                    easy_apply=search.easy_apply,
                )
            except Exception as exc:
                errors.append(f"{search.name}: {exc}")
                continue

            job_ids = payload.get("job_ids")
            if not isinstance(job_ids, list):
                continue
            for job_id in job_ids:
                if new_jobs >= remaining:
                    break
                external_id = str(job_id)
                existing = session.scalars(
                    select(JobPosting).where(
                        JobPosting.source == "linkedin",
                        JobPosting.external_id == external_id,
                    )
                ).first()
                if existing is not None:
                    skipped += 1
                    continue
                try:
                    details = await mcp.get_job_details(external_id)
                    apply_payload = await mcp.get_job_apply_url(external_id)
                    details = dict(details)
                    details["apply"] = apply_payload.get("apply", {"type": "unknown"})
                    url = str(
                        details.get("url") or f"https://www.linkedin.com/jobs/view/{external_id}/"
                    )
                    raw_text = ""
                    sections = details.get("sections")
                    if isinstance(sections, dict):
                        raw_text = str(sections.get("job_posting") or "")
                    detected_type = detect_apply_type(details, raw_text)
                    if detected_type != "easy_apply":
                        if detected_type == "unknown":
                            skipped_unknown += 1
                        else:
                            skipped_external += 1
                        continue
                    parsed = await gemini.extract_job(raw_text, external_id, url)
                    if parsed is None:
                        parsed = parse_job_payload(details, external_id, url)
                    else:
                        parsed = parse_job_payload(details, external_id, url, parsed)

                    if settings.remote_only and parsed.work_mode != "remote":
                        skipped_non_remote += 1
                        continue

                    company = _get_or_create_company(session, parsed.company)
                    job = JobPosting(
                        source="linkedin",
                        external_id=external_id,
                        url=url,
                        title=parsed.title,
                        company_id=company.id if company else None,
                        company_name=parsed.company,
                        location=parsed.location,
                        work_mode=parsed.work_mode,
                        employment_type=parsed.employment_type,
                        seniority=parsed.seniority,
                        salary_min=parsed.salary_min,
                        salary_max=parsed.salary_max,
                        salary_currency=parsed.salary_currency,
                        description=parsed.description,
                        requirements=parsed.requirements,
                        apply_type=parsed.apply_type,
                        job_family=parsed.job_family,
                        raw_text=parsed.raw_text,
                        raw_payload=details,
                        fingerprint=hashlib.sha256(external_id.encode()).hexdigest(),
                        search_profile_id=search.id,
                    )
                    session.add(job)
                    session.flush()

                    session.execute(delete(JobSkill).where(JobSkill.job_id == job.id))
                    skill_rows = {
                        row.slug: row
                        for row in session.scalars(
                            select(Skill).where(
                                Skill.slug.in_(parsed.skills + parsed.required_skills)
                            )
                        ).all()
                    }
                    for slug, name, kind in job_skill_tuples(parsed):
                        skill = skill_rows.get(slug)
                        if skill is not None:
                            session.add(
                                JobSkill(
                                    job_id=job.id,
                                    skill_id=skill.id,
                                    requirement_type=kind,
                                    weight=1.0,
                                    evidence=name,
                                )
                            )
                    _score_and_store(session, candidate, search, job, parsed)
                    new_jobs += 1
                    # Libera el lock para que el heartbeat y el panel vean el avance.
                    session.commit()
                except Exception as exc:
                    session.rollback()
                    errors.append(f"Oferta {external_id}: {exc}")

            search.last_run_at = datetime.now(UTC)
            session.commit()
            if new_jobs >= remaining:
                break
        await mcp.close_session()

    session.flush()
    return {
        "searches": len(searches),
        "jobs": new_jobs,
        "skipped": skipped,
        "skipped_external": skipped_external,
        "skipped_unknown": skipped_unknown,
        "skipped_non_remote": skipped_non_remote,
        "remaining_today": max(0, remaining - new_jobs),
        "errors": errors,
        "message": (
            f"Se agregaron {new_jobs} ofertas Easy Apply remotas. "
            f"Se descartaron {skipped_external} externas, "
            f"{skipped_unknown} sin clasificar y {skipped_non_remote} no remotas."
        ),
    }


def mark_existing_applications(session: Session, candidate_id: str, applied_ids: set[str]) -> int:
    """Marca ofertas ya aplicadas sin volver a enviar nada."""
    if not applied_ids:
        return 0
    jobs = session.scalars(
        select(JobPosting).where(
            JobPosting.source == "linkedin",
            JobPosting.external_id.in_(applied_ids),
        )
    ).all()
    changed = 0
    for job in jobs:
        application = session.scalars(
            select(Application).where(
                Application.candidate_id == candidate_id,
                Application.job_id == job.id,
            )
        ).first()
        if application is None:
            application = Application(
                candidate_id=candidate_id,
                job_id=job.id,
                status="submitted",
                mode="linkedin",
            )
            session.add(application)
            changed += 1
        elif application.status != "submitted":
            application.status = "submitted"
            changed += 1
    return changed


def latest_run(session: Session) -> AutomationRun | None:
    return session.scalars(select(AutomationRun).order_by(AutomationRun.created_at.desc())).first()


def rescore_jobs(session: Session, settings: Settings) -> int:
    """Recalcula los scores existentes sin volver a consultar LinkedIn."""
    candidate = get_or_create_candidate(session)
    searches = {
        row.id: row
        for row in session.scalars(
            select(SearchProfile).where(SearchProfile.candidate_id == candidate.id)
        ).all()
    }
    default_search = next(iter(searches.values()), None)
    jobs = session.scalars(select(JobPosting)).all()
    updated = 0
    for job in jobs:
        search = searches.get(job.search_profile_id or "") or default_search
        if search is None:
            continue
        snapshot = _candidate_snapshot(session, candidate, search)
        job_snapshot = JobSnapshot(
            title=job.title,
            company=job.company_name,
            location=job.location,
            work_mode=job.work_mode,
            description=job.description,
            requirements=job.requirements,
            job_family=job.job_family,
            apply_type=job.apply_type,
        )
        skill_rows = session.execute(
            select(Skill.slug, Skill.name, JobSkill.requirement_type)
            .join(JobSkill, JobSkill.skill_id == Skill.id)
            .where(JobSkill.job_id == job.id)
        ).all()
        result = score_job(
            snapshot,
            job_snapshot,
            [(str(slug), str(name), str(kind)) for slug, name, kind in skill_rows],
            search.min_score,
        )
        session.execute(
            delete(JobScore).where(
                JobScore.job_id == job.id,
                JobScore.candidate_id == candidate.id,
            )
        )
        session.add(
            JobScore(
                job_id=job.id,
                candidate_id=candidate.id,
                search_profile_id=search.id,
                rubric_version=result.rubric_version,
                total=result.total,
                band=result.band,
                components=[component.as_dict() for component in result.components],
                matched_skills=result.matched_skills,
                missing_skills=result.missing_skills,
                risks=result.risks,
                summary=result.summary,
                model="rubrica-local",
            )
        )
        updated += 1
    session.commit()
    return updated
