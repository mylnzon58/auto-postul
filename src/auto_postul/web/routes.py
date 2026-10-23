"""Rutas HTML, formularios y API mínima."""

from __future__ import annotations

import hmac
import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from auto_postul.application.queue import enqueue, find_active
from auto_postul.config import Settings, get_settings
from auto_postul.db.models import (
    AnswerBank,
    Application,
    ApplicationEvent,
    ApplicationField,
    Artifact,
    AutomationRun,
    Candidate,
    CandidateDocument,
    CandidateSkill,
    Education,
    Experience,
    JobPosting,
    JobScore,
    JobSkill,
    Language,
    SearchProfile,
    Skill,
)
from auto_postul.db.seed import create_candidate, get_or_create_candidate, set_active_candidate
from auto_postul.domain.enums import ApplicationStatus, TaskKind, TaskStatus
from auto_postul.web.deps import get_db

logger = logging.getLogger(__name__)
router = APIRouter()
templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

TZ = ZoneInfo("America/Argentina/Cordoba")


def _dt(value: datetime | None) -> str:
    if value is None:
        return "—"
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(TZ).strftime("%d/%m/%Y %H:%M")


def _band_label(value: str) -> str:
    return {
        "muy_alta": "Muy alta",
        "alta": "Alta",
        "media": "Media",
        "media_baja": "Media-baja",
        "baja": "Baja",
    }.get(value, value or "Sin score")


def _band_class(value: str) -> str:
    return {
        "muy_alta": "band-very-high",
        "alta": "band-high",
        "media": "band-medium",
        "media_baja": "band-low",
        "baja": "band-very-low",
    }.get(value, "band-none")


def _status_label(value: str) -> str:
    return {
        "detected": "Detectada",
        "scored": "Puntuada",
        "shortlisted": "Preseleccionada",
        "preparing": "Preparando",
        "needs_input": "Falta un dato",
        "ready_for_review": "Lista para revisar",
        "submitting": "Enviando",
        "submitted": "Enviada",
        "failed": "Falló",
        "skipped": "Omitida",
        "submission_unknown": "Verificar manualmente",
        "queued": "En cola",
        "running": "Ejecutando",
        "done": "Terminado",
    }.get(value, value)


def _task_label(value: str) -> str:
    return {
        "scan": "Escaneo",
        "prepare": "Preparación",
        "submit": "Envío",
        "login": "Login LinkedIn",
    }.get(value, value)


templates.env.filters["dt"] = _dt
templates.env.filters["band_label"] = _band_label
templates.env.filters["band_class"] = _band_class
templates.env.filters["status_label"] = _status_label
templates.env.filters["task_label"] = _task_label


def _flash(request: Request, message: str, kind: str = "info") -> None:
    request.session["flash"] = {"message": message, "kind": kind}


async def _csrf(request: Request) -> None:
    expected = request.session.get("csrf")
    provided = request.headers.get("x-csrf-token")
    if not provided and request.headers.get("content-type", "").startswith(
        ("application/x-www-form-urlencoded", "multipart/form-data")
    ):
        form = await request.form()
        provided = str(form.get("_csrf") or "")
    if not expected or not provided or not hmac.compare_digest(str(provided), str(expected)):
        raise HTTPException(status_code=403, detail="Token CSRF inválido.")


def _render(request: Request, name: str, **context: Any) -> HTMLResponse:
    settings = get_settings()
    context.setdefault("app_name", "AutoPostul")
    context.setdefault("live_submit", settings.live_submit_enabled)
    context.setdefault("dry_run", settings.apply_dry_run)
    context.setdefault("gemini_enabled", settings.gemini_enabled)
    context.setdefault("flash", request.session.pop("flash", None))
    context.setdefault("csrf", request.session.get("csrf", ""))
    context.setdefault("nav", "dashboard")
    context.setdefault("linkedin_session", _linkedin_session_present(settings))
    return templates.TemplateResponse(request=request, name=name, context=context, status_code=200)


def _score_map(session: Session, candidate_id: str) -> dict[str, JobScore]:
    rows = session.scalars(
        select(JobScore)
        .where(JobScore.candidate_id == candidate_id)
        .order_by(JobScore.created_at.desc())
    ).all()
    result: dict[str, JobScore] = {}
    for row in rows:
        result.setdefault(row.job_id, row)
    return result


def _application_map(session: Session, candidate_id: str) -> dict[str, Application]:
    rows = session.scalars(
        select(Application).where(Application.candidate_id == candidate_id)
    ).all()
    return {row.job_id: row for row in rows}


def _linkedin_session_present(settings: Settings) -> bool:
    parent = settings.linkedin_parent_dir
    if (parent / "cookies.json").exists():
        return True
    profile = settings.linkedin_profile_dir
    try:
        return any(profile.iterdir())
    except OSError:
        return False


def _scan_used_today(session: Session) -> int:
    today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    value = session.scalar(
        select(func.count(AutomationRun.id)).where(
            AutomationRun.kind == TaskKind.SCAN.value,
            AutomationRun.created_at >= today,
        )
    )
    return int(value or 0)


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, session: Session = Depends(get_db)) -> HTMLResponse:
    candidate = get_or_create_candidate(session)
    scores = _score_map(session, candidate.id)
    jobs = session.scalars(select(JobPosting).order_by(JobPosting.created_at.desc())).all()
    applications = _application_map(session, candidate.id)
    high = sum(1 for job in jobs if job.id in scores and scores[job.id].total >= 75)
    ready = sum(
        1 for app in applications.values() if app.status == ApplicationStatus.READY_FOR_REVIEW.value
    )
    submitted = sum(
        1 for app in applications.values() if app.status == ApplicationStatus.SUBMITTED.value
    )
    runs = session.scalars(
        select(AutomationRun).order_by(AutomationRun.created_at.desc()).limit(8)
    ).all()
    top_jobs = sorted(
        [job for job in jobs if job.id in scores],
        key=lambda job: scores[job.id].total,
        reverse=True,
    )[:5]
    documents = session.scalars(
        select(CandidateDocument).where(CandidateDocument.candidate_id == candidate.id)
    ).all()
    onboarding = not candidate.full_name or not documents
    return _render(
        request,
        "dashboard.html",
        nav="dashboard",
        candidate=candidate,
        total_jobs=len(jobs),
        high=high,
        ready=ready,
        submitted=submitted,
        runs=runs,
        top_jobs=top_jobs,
        scores=scores,
        applications=applications,
        onboarding=onboarding,
        linkedin_session=_linkedin_session_present(get_settings()),
        scan_used=_scan_used_today(session),
        scan_limit=get_settings().daily_scan_limit,
    )


@router.get("/jobs", response_class=HTMLResponse)
def jobs_page(
    request: Request,
    q: str = "",
    band: str = "",
    apply_type: str = "",
    session: Session = Depends(get_db),
) -> HTMLResponse:
    candidate = get_or_create_candidate(session)
    scores = _score_map(session, candidate.id)
    applications = _application_map(session, candidate.id)
    rows = list(session.scalars(select(JobPosting).order_by(JobPosting.created_at.desc())).all())
    if q.strip():
        needle = q.strip().casefold()
        rows = [
            row
            for row in rows
            if needle in row.title.casefold()
            or needle in row.company_name.casefold()
            or needle in row.description.casefold()
        ]
    if band:
        rows = [row for row in rows if row.id in scores and scores[row.id].band == band]
    if apply_type:
        rows = [row for row in rows if row.apply_type == apply_type]
    rows.sort(key=lambda row: scores[row.id].total if row.id in scores else -1, reverse=True)
    return _render(
        request,
        "jobs.html",
        nav="jobs",
        jobs=rows[:200],
        scores=scores,
        applications=applications,
        q=q,
        band=band,
        apply_type=apply_type,
    )


@router.get("/jobs/{job_id}", response_class=HTMLResponse)
def job_detail(job_id: str, request: Request, session: Session = Depends(get_db)) -> HTMLResponse:
    candidate = get_or_create_candidate(session)
    job = session.get(JobPosting, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Oferta no encontrada.")
    score = _score_map(session, candidate.id).get(job.id)
    application = session.scalars(
        select(Application).where(
            Application.candidate_id == candidate.id, Application.job_id == job.id
        )
    ).first()
    skill_rows = session.execute(
        select(Skill.name, JobSkill.requirement_type)
        .join(JobSkill, JobSkill.skill_id == Skill.id)
        .where(JobSkill.job_id == job.id)
    ).all()
    return _render(
        request,
        "job_detail.html",
        nav="jobs",
        job=job,
        score=score,
        application=application,
        skills=skill_rows,
        candidate=candidate,
    )


@router.post("/jobs/{job_id}/prepare")
async def prepare_job(
    request: Request, job_id: str, session: Session = Depends(get_db)
) -> RedirectResponse:
    await _csrf(request)
    job = session.get(JobPosting, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Oferta no encontrada.")
    if job.apply_type != "easy_apply":
        _flash(request, "Esta oferta no es Easy Apply. No se prepara envío automático.", "warning")
        return RedirectResponse(url=f"/jobs/{job_id}", status_code=303)
    active = find_active(session, TaskKind.PREPARE)
    if active is not None:
        _flash(request, "Ya hay una preparación en curso. Esperá a que termine.", "warning")
        return RedirectResponse(url="/activity", status_code=303)
    enqueue(session, TaskKind.PREPARE, {"job_id": job_id})
    _flash(
        request,
        "Preparación encolada. El worker abrirá el navegador y completará el formulario.",
        "success",
    )
    return RedirectResponse(url="/activity", status_code=303)


@router.get("/applications", response_class=HTMLResponse)
def applications_page(request: Request, session: Session = Depends(get_db)) -> HTMLResponse:
    candidate = get_or_create_candidate(session)
    applications = session.scalars(
        select(Application)
        .where(Application.candidate_id == candidate.id)
        .order_by(Application.updated_at.desc())
    ).all()
    jobs = {job.id: job for job in session.scalars(select(JobPosting)).all()}
    scores = _score_map(session, candidate.id)
    return _render(
        request,
        "applications.html",
        nav="applications",
        applications=applications,
        jobs=jobs,
        scores=scores,
    )


@router.get("/applications/{application_id}", response_class=HTMLResponse)
def application_detail(
    application_id: str, request: Request, session: Session = Depends(get_db)
) -> HTMLResponse:
    candidate = get_or_create_candidate(session)
    application = session.get(Application, application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Postulación no encontrada.")
    job = session.get(JobPosting, application.job_id)
    score = _score_map(session, candidate.id).get(application.job_id)
    fields = session.scalars(
        select(ApplicationField).where(ApplicationField.application_id == application.id)
    ).all()
    events = session.scalars(
        select(ApplicationEvent)
        .where(ApplicationEvent.application_id == application.id)
        .order_by(ApplicationEvent.created_at.desc())
    ).all()
    artifacts = session.scalars(
        select(Artifact)
        .where(Artifact.application_id == application.id)
        .order_by(Artifact.created_at.desc())
    ).all()
    unresolved = [field for field in fields if field.required and field.status == "pending"]
    return _render(
        request,
        "application_review.html",
        nav="applications",
        application=application,
        job=job,
        score=score,
        fields=fields,
        events=events,
        artifacts=artifacts,
        unresolved=unresolved,
    )


@router.post("/applications/{application_id}/submit")
async def submit_application(
    request: Request, application_id: str, session: Session = Depends(get_db)
) -> RedirectResponse:
    await _csrf(request)
    form = await request.form()
    confirmation = str(form.get("confirmation") or "")
    application = session.get(Application, application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Postulación no encontrada.")
    if confirmation.strip().upper() != "ENVIAR":
        _flash(request, "Escribí ENVIAR para confirmar.", "warning")
        return RedirectResponse(url=f"/applications/{application_id}", status_code=303)
    active = find_active(session, TaskKind.SUBMIT)
    if active is not None:
        _flash(request, "Ya hay un envío en curso.", "warning")
        return RedirectResponse(url=f"/applications/{application_id}", status_code=303)
    enqueue(
        session,
        TaskKind.SUBMIT,
        {"application_id": application_id, "confirmation": confirmation},
    )
    _flash(
        request,
        "Envío encolado. Se pedirá confirmación final en el navegador si corresponde.",
        "success",
    )
    return RedirectResponse(url=f"/applications/{application_id}", status_code=303)


@router.get("/candidates", response_class=HTMLResponse)
def candidates_page(request: Request, session: Session = Depends(get_db)) -> HTMLResponse:
    active = get_or_create_candidate(session)
    rows = session.scalars(select(Candidate).order_by(Candidate.created_at)).all()
    return _render(request, "candidates.html", nav="candidates", candidates=rows, active=active)


@router.post("/candidates")
async def create_candidate_route(
    request: Request, session: Session = Depends(get_db)
) -> RedirectResponse:
    await _csrf(request)
    form = await request.form()
    full_name = str(form.get("full_name") or "").strip()
    headline = str(form.get("headline") or "").strip()
    if not full_name:
        _flash(request, "El nombre es obligatorio para crear un perfil.", "warning")
        return RedirectResponse(url="/candidates", status_code=303)
    create_candidate(session, full_name=full_name, headline=headline)
    _flash(request, "Perfil creado. Importá su CV y revisá las respuestas.", "success")
    return RedirectResponse(url="/profile", status_code=303)


@router.post("/candidates/{candidate_id}/select")
async def select_candidate(
    request: Request, candidate_id: str, session: Session = Depends(get_db)
) -> RedirectResponse:
    await _csrf(request)
    candidate = session.get(Candidate, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Perfil no encontrado.")
    set_active_candidate(session, candidate)
    _flash(request, f"Perfil activo: {candidate.full_name or 'sin nombre'}.", "success")
    return RedirectResponse(url="/profile", status_code=303)


@router.get("/profile", response_class=HTMLResponse)
def profile_page(request: Request, session: Session = Depends(get_db)) -> HTMLResponse:
    candidate = get_or_create_candidate(session)
    documents = session.scalars(
        select(CandidateDocument)
        .where(CandidateDocument.candidate_id == candidate.id)
        .order_by(CandidateDocument.created_at.desc())
    ).all()
    experiences = session.scalars(
        select(Experience)
        .where(Experience.candidate_id == candidate.id)
        .order_by(Experience.start_date.desc())
    ).all()
    education = session.scalars(
        select(Education).where(Education.candidate_id == candidate.id)
    ).all()
    languages = session.scalars(select(Language).where(Language.candidate_id == candidate.id)).all()
    skills = session.execute(
        select(Skill.name, Skill.category, CandidateSkill.evidence)
        .join(CandidateSkill, CandidateSkill.skill_id == Skill.id)
        .where(CandidateSkill.candidate_id == candidate.id)
        .order_by(Skill.category, Skill.name)
    ).all()
    answers = session.scalars(
        select(AnswerBank).where(AnswerBank.candidate_id == candidate.id).order_by(AnswerBank.key)
    ).all()
    return _render(
        request,
        "profile.html",
        nav="profile",
        candidate=candidate,
        documents=documents,
        experiences=experiences,
        education=education,
        languages=languages,
        skills=skills,
        answers=answers,
    )


@router.post("/profile")
async def update_profile(request: Request, session: Session = Depends(get_db)) -> RedirectResponse:
    await _csrf(request)
    candidate = get_or_create_candidate(session)
    form = await request.form()
    for field in (
        "full_name",
        "email",
        "phone",
        "location",
        "headline",
        "summary",
        "linkedin_url",
        "github_url",
        "portfolio_url",
        "english_level",
    ):
        if field in form:
            setattr(candidate, field, str(form.get(field) or "").strip())
    if "years_experience" in form:
        try:
            candidate.years_experience = float(str(form.get("years_experience") or 0))
        except ValueError:
            candidate.years_experience = 0.0
    _flash(request, "Perfil actualizado.", "success")
    return RedirectResponse(url="/profile", status_code=303)


@router.post("/profile/import")
async def import_profile(
    request: Request,
    file: UploadFile | None = File(default=None),
    session: Session = Depends(get_db),
) -> RedirectResponse:
    await _csrf(request)
    settings = get_settings()
    from auto_postul.application.cv_import import discover_root_pdfs, import_cv_from_path

    paths: list[Path] = []
    if file is not None and file.filename:
        uploads = settings.data_dir / "uploads"
        uploads.mkdir(parents=True, exist_ok=True)
        safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", Path(file.filename).name)
        target = uploads / safe_name
        target.write_bytes(await file.read())
        paths = [target]
    else:
        paths = discover_root_pdfs(settings)
    if not paths:
        _flash(request, "No encontré PDFs en la raíz. Subí uno desde este formulario.", "warning")
        return RedirectResponse(url="/profile", status_code=303)
    imported = 0
    for path in paths:
        try:
            await import_cv_from_path(session, path, settings)
            imported += 1
        except Exception as exc:
            logger.warning("No se pudo importar %s: %s", path, exc)
            _flash(request, f"No se pudo importar {path.name}: {exc}", "error")
    if imported:
        _flash(
            request, f"CV importado ({imported}). Revisá los datos antes de postular.", "success"
        )
    return RedirectResponse(url="/profile", status_code=303)


@router.post("/profile/answers")
async def update_answers(request: Request, session: Session = Depends(get_db)) -> RedirectResponse:
    await _csrf(request)
    candidate = get_or_create_candidate(session)
    form = await request.form()
    rows = session.scalars(select(AnswerBank).where(AnswerBank.candidate_id == candidate.id)).all()
    for row in rows:
        answer_key = f"answer_{row.id}"
        if answer_key in form:
            row.answer = str(form.get(answer_key) or "").strip()
        row.verified = f"verified_{row.id}" in form
    _flash(request, "Banco de respuestas actualizado.", "success")
    return RedirectResponse(url="/profile#respuestas", status_code=303)


@router.get("/searches", response_class=HTMLResponse)
def searches_page(request: Request, session: Session = Depends(get_db)) -> HTMLResponse:
    candidate = get_or_create_candidate(session)
    searches = session.scalars(
        select(SearchProfile)
        .where(SearchProfile.candidate_id == candidate.id)
        .order_by(SearchProfile.created_at)
    ).all()
    return _render(request, "searches.html", nav="searches", searches=searches)


@router.post("/searches")
async def create_search(request: Request, session: Session = Depends(get_db)) -> RedirectResponse:
    await _csrf(request)
    candidate = get_or_create_candidate(session)
    form = await request.form()
    name = str(form.get("name") or "").strip()
    keywords = str(form.get("keywords") or "").strip()
    if not name or not keywords:
        _flash(request, "Nombre y palabras clave son obligatorios.", "warning")
        return RedirectResponse(url="/searches", status_code=303)
    session.add(
        SearchProfile(
            candidate_id=candidate.id,
            name=name[:160],
            keywords=keywords[:500],
            location=str(form.get("location") or "Argentina"),
            easy_apply=True,
            date_posted=str(form.get("date_posted") or "past_week"),
            work_type=str(form.get("work_type") or "remote"),
            job_type="full_time",
            max_pages=1,
            min_score=int(str(form.get("min_score") or 60)),
            tracks=[],
            enabled=True,
        )
    )
    _flash(request, "Búsqueda creada.", "success")
    return RedirectResponse(url="/searches", status_code=303)


@router.post("/searches/{search_id}/toggle")
async def toggle_search(
    request: Request, search_id: str, session: Session = Depends(get_db)
) -> RedirectResponse:
    await _csrf(request)
    search = session.get(SearchProfile, search_id)
    if search is not None:
        search.enabled = not search.enabled
    return RedirectResponse(url="/searches", status_code=303)


@router.post("/searches/{search_id}/delete")
async def delete_search(
    request: Request, search_id: str, session: Session = Depends(get_db)
) -> RedirectResponse:
    await _csrf(request)
    session.execute(delete(SearchProfile).where(SearchProfile.id == search_id))
    _flash(request, "Búsqueda eliminada.", "success")
    return RedirectResponse(url="/searches", status_code=303)


@router.post("/actions/scan")
async def action_scan(request: Request, session: Session = Depends(get_db)) -> RedirectResponse:
    await _csrf(request)
    settings = get_settings()
    if _scan_used_today(session) >= settings.daily_scan_limit:
        _flash(request, "Límite diario de escaneos alcanzado.", "warning")
        return RedirectResponse(url="/", status_code=303)
    if find_active(session, TaskKind.SCAN) is not None:
        _flash(request, "Ya hay un escaneo en curso.", "warning")
        return RedirectResponse(url="/", status_code=303)
    enqueue(session, TaskKind.SCAN, {})
    _flash(request, "Escaneo encolado. El worker leerá LinkedIn y puntuará ofertas.", "success")
    return RedirectResponse(url="/activity", status_code=303)


@router.get("/activity", response_class=HTMLResponse)
def activity_page(request: Request, session: Session = Depends(get_db)) -> HTMLResponse:
    runs = session.scalars(
        select(AutomationRun).order_by(AutomationRun.created_at.desc()).limit(50)
    ).all()
    events = session.scalars(
        select(ApplicationEvent).order_by(ApplicationEvent.created_at.desc()).limit(50)
    ).all()
    applications = {app.id: app for app in session.scalars(select(Application)).all()}
    jobs = {job.id: job for job in session.scalars(select(JobPosting)).all()}
    return _render(
        request,
        "activity.html",
        nav="activity",
        runs=runs,
        events=events,
        applications=applications,
        jobs=jobs,
    )


@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request, session: Session = Depends(get_db)) -> HTMLResponse:
    settings = get_settings()
    profile_present = _linkedin_session_present(settings)
    active = find_active(session)
    return _render(
        request,
        "settings.html",
        nav="settings",
        settings=settings,
        profile_present=profile_present,
        active=active,
    )


@router.post("/settings/login-linkedin")
async def login_linkedin(request: Request, session: Session = Depends(get_db)) -> RedirectResponse:
    await _csrf(request)
    if find_active(session, TaskKind.LOGIN) is not None:
        _flash(request, "Ya hay un login en curso.", "warning")
        return RedirectResponse(url="/settings", status_code=303)
    enqueue(session, TaskKind.LOGIN, {})
    _flash(
        request,
        "Login encolado. Se abrirá una ventana de Chromium; completá LinkedIn y esperá.",
        "success",
    )
    return RedirectResponse(url="/settings", status_code=303)


@router.get("/artifacts/{application_id}/{filename}")
def artifact_file(
    application_id: str, filename: str, session: Session = Depends(get_db)
) -> FileResponse:
    if Path(filename).name != filename:
        raise HTTPException(status_code=400, detail="Nombre inválido.")
    record = session.scalars(
        select(Artifact).where(
            Artifact.application_id == application_id,
            Artifact.path.like(f"%{filename}"),
        )
    ).first()
    if record is None:
        raise HTTPException(status_code=404, detail="Artefacto no encontrado.")
    path = Path(record.path)
    artifacts_dir = get_settings().artifacts_dir
    if not path.exists() or artifacts_dir not in path.parents:
        raise HTTPException(status_code=404, detail="Archivo no encontrado.")
    return FileResponse(path)


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request) -> HTMLResponse:
    settings = get_settings()
    if not settings.app_password or request.session.get("auth"):
        return RedirectResponse(url="/", status_code=303)  # type: ignore[return-value]
    return _render(request, "login.html", nav="login")


@router.post("/login")
async def login_submit(request: Request) -> RedirectResponse:
    await _csrf(request)
    settings = get_settings()
    form = await request.form()
    password = str(form.get("password") or "")
    if settings.app_password and hmac.compare_digest(password, settings.app_password):
        request.session["auth"] = True
        return RedirectResponse(url="/", status_code=303)
    _flash(request, "Contraseña incorrecta.", "error")
    return RedirectResponse(url="/login", status_code=303)


@router.post("/logout")
async def logout(request: Request) -> RedirectResponse:
    await _csrf(request)
    request.session.clear()
    return RedirectResponse(url="/", status_code=303)


@router.get("/api/health")
def health(session: Session = Depends(get_db)) -> JSONResponse:
    settings = get_settings()
    db_ok = True
    try:
        session.execute(select(1))
    except Exception:
        db_ok = False
    queued = session.scalar(
        select(func.count(AutomationRun.id)).where(AutomationRun.status == TaskStatus.QUEUED.value)
    )
    running = session.scalar(
        select(func.count(AutomationRun.id)).where(AutomationRun.status == TaskStatus.RUNNING.value)
    )
    return JSONResponse(
        {
            "ok": db_ok,
            "database": db_ok,
            "app": "AutoPostul",
            "version": "0.1.0",
            "gemini": settings.gemini_enabled,
            "linkedin_session": _linkedin_session_present(settings),
            "dry_run": settings.apply_dry_run,
            "live_submit": settings.live_submit_enabled,
            "queued": int(queued or 0),
            "running": int(running or 0),
        }
    )
