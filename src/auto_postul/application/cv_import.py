"""Caso de uso: importar un CV sin modificar el archivo original."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from auto_postul.config import Settings
from auto_postul.db.models import (
    AnswerBank,
    Candidate,
    CandidateDocument,
    CandidateSkill,
    Certification,
    Education,
    Experience,
    Language,
    Skill,
)
from auto_postul.db.seed import get_or_create_candidate
from auto_postul.domain.cv import extract_pdf_text, parse_cv_text
from auto_postul.domain.schemas import CvData
from auto_postul.infrastructure.gemini import GeminiService


def discover_root_pdfs(settings: Settings) -> list[Path]:
    """Busca PDFs en la raíz del proyecto, sin entrar en docs ni datos."""
    return sorted(
        path
        for path in settings.cv_input_dir.glob("*.pdf")
        if path.is_file() and "sample" not in path.name.casefold()
    )


def _safe_filename(name: str, digest: str) -> str:
    stem = "".join(char for char in Path(name).stem if char.isalnum() or char in "-_")[:60]
    return f"{stem or 'cv'}-{digest[:12]}.pdf"


async def import_cv_from_path(
    session: Session,
    path: Path,
    settings: Settings,
    *,
    replace_existing: bool = True,
) -> Candidate:
    """Copia el PDF, extrae texto, estructura y actualiza el perfil."""
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    try:
        text = extract_pdf_text(path)
    except ValueError:
        text = ""

    structured: CvData | None = None
    if settings.gemini_enabled:
        structured = await GeminiService(settings).extract_cv(text, data)
    if structured is None and not text:
        raise ValueError(
            "El PDF no tiene texto y Gemini no está disponible. Configurá GEMINI_API_KEY o usá un PDF digital."
        )
    cv = structured or parse_cv_text(text)

    candidate = get_or_create_candidate(session)
    candidate.full_name = cv.full_name or candidate.full_name
    candidate.email = cv.email or candidate.email
    candidate.phone = cv.phone or candidate.phone
    candidate.location = cv.location or candidate.location
    candidate.headline = cv.headline or candidate.headline
    candidate.summary = cv.summary or candidate.summary
    candidate.linkedin_url = cv.linkedin_url or candidate.linkedin_url
    candidate.github_url = cv.github_url or candidate.github_url
    candidate.portfolio_url = cv.portfolio_url or candidate.portfolio_url
    candidate.years_experience = cv.years_experience or candidate.years_experience
    candidate.english_level = cv.english_level or candidate.english_level

    parts = cv.full_name.split()
    identity = {
        "first_name": parts[0] if parts else "",
        "last_name": " ".join(parts[1:]) if len(parts) > 1 else "",
        "email": cv.email,
        "phone": cv.phone,
        "location": cv.location,
        "country": "Argentina" if "argentina" in cv.location.casefold() else "",
        "english_level": cv.english_level,
        "linkedin": cv.linkedin_url,
        "github": cv.github_url,
    }
    for key, value in identity.items():
        if not value:
            continue
        answer = session.scalars(
            select(AnswerBank).where(
                AnswerBank.candidate_id == candidate.id,
                AnswerBank.key == key,
            )
        ).first()
        if answer is None:
            answer = AnswerBank(
                candidate_id=candidate.id,
                key=key,
                question_pattern=key,
                answer=value,
                verified=True,
                notes="Extraído del CV. Revisar en la UI.",
            )
            session.add(answer)
        else:
            answer.answer = value
            answer.verified = True
            answer.notes = "Extraído del CV. Revisar en la UI."

    existing = session.scalars(
        select(CandidateDocument).where(CandidateDocument.sha256 == digest)
    ).first()
    if existing is None:
        destination = settings.documents_dir / _safe_filename(path.name, digest)
        if not destination.exists():
            shutil.copyfile(path, destination)
        session.execute(
            update(CandidateDocument)
            .where(CandidateDocument.candidate_id == candidate.id)
            .values(is_primary=False)
        )
        session.add(
            CandidateDocument(
                candidate_id=candidate.id,
                kind="cv",
                filename=path.name,
                stored_path=str(destination),
                sha256=digest,
                mime_type="application/pdf",
                text_content=text,
                is_primary=True,
            )
        )
    else:
        existing.text_content = text
        existing.is_primary = True

    if replace_existing:
        for model in (Experience, Education, Certification, Language, CandidateSkill):
            session.execute(delete(model).where(model.candidate_id == candidate.id))

    for experience in cv.experiences:
        session.add(
            Experience(
                candidate_id=candidate.id,
                company=experience.company,
                title=experience.title,
                start_date=experience.start_date,
                end_date=experience.end_date,
                is_current=experience.is_current,
                description=experience.description,
            )
        )
    for education_item in cv.education:
        session.add(
            Education(
                candidate_id=candidate.id,
                institution=education_item.institution,
                degree=education_item.degree,
                field=education_item.field,
                start_date=education_item.start_date,
                end_date=education_item.end_date,
                status=education_item.status,
                description=education_item.description,
            )
        )
    for name, level in cv.languages:
        session.add(Language(candidate_id=candidate.id, name=name, level=level))
    for name in cv.certifications:
        if name.strip():
            session.add(Certification(candidate_id=candidate.id, name=name[:300]))

    skills_by_slug = {
        row.slug: row
        for row in session.scalars(select(Skill).where(Skill.slug.in_(cv.skills))).all()
    }
    for slug in cv.skills:
        skill = skills_by_slug.get(slug)
        if skill is not None:
            session.add(
                CandidateSkill(
                    candidate_id=candidate.id,
                    skill_id=skill.id,
                    level="declarada",
                    source="cv",
                    evidence="Detectada en el CV importado.",
                )
            )
    session.flush()
    return candidate
