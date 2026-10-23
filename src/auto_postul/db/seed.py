"""Seed idempotente de catálogos y valores iniciales."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from auto_postul.config import get_settings
from auto_postul.db.models import (
    AnswerBank,
    Candidate,
    CandidatePreference,
    SearchProfile,
    Setting,
    Skill,
    SkillAlias,
)
from auto_postul.db.session import init_db, session_scope
from auto_postul.domain.skills import SKILLS

DEFAULT_ANSWERS: tuple[tuple[str, str], ...] = (
    ("first_name", "Primer nombre"),
    ("last_name", "Apellido"),
    ("email", "Email de contacto"),
    ("phone", "Teléfono de contacto"),
    ("location", "Ciudad o región"),
    ("country", "País de residencia"),
    ("work_authorization", "¿Tienes autorización para trabajar en este país?"),
    ("sponsorship", "¿Requerís patrocinio de visa?"),
    ("remote", "¿Aceptas trabajo remoto?"),
    ("english_level", "Nivel de inglés"),
    ("availability", "Disponibilidad para comenzar"),
    ("notice_period", "Preaviso"),
    ("salary_expectation", "Pretensión salarial"),
    ("linkedin", "Perfil de LinkedIn"),
    ("github", "Perfil de GitHub"),
)

DEFAULT_SEARCHES: tuple[dict[str, object], ...] = (
    {
        "name": "AI Product Engineer",
        "keywords": "AI Product Engineer",
        "tracks": ["ai_product_engineering", "ai_assisted_development"],
    },
    {
        "name": "Full Stack remoto",
        "keywords": "Full Stack Developer",
        "tracks": ["full_stack"],
    },
    {
        "name": "Google Ads / SEM",
        "keywords": "Google Ads Search specialist",
        "tracks": ["google_ads_sem", "analytics_measurement"],
    },
    {
        "name": "Landing pages y SEO técnico",
        "keywords": "landing page developer SEO técnico",
        "tracks": ["seo_landing_cro"],
    },
    {
        "name": "Automatización con IA",
        "keywords": "AI automation engineer MCP",
        "tracks": ["automation_mcp"],
    },
)


def seed_skills(session: Session) -> None:
    """Inserta skills y alias solo cuando faltan."""
    by_slug = {row.slug: row for row in session.scalars(select(Skill)).all()}
    by_alias = {row.alias.casefold(): row for row in session.scalars(select(SkillAlias)).all()}

    for definition in SKILLS:
        skill = by_slug.get(definition.slug)
        if skill is None:
            skill = Skill(
                slug=definition.slug,
                name=definition.name,
                category=definition.category,
            )
            session.add(skill)
            session.flush()
            by_slug[definition.slug] = skill

        aliases = {definition.name, definition.slug, *definition.aliases}
        for alias in aliases:
            key = alias.casefold()
            if key not in by_alias:
                row = SkillAlias(skill_id=skill.id, alias=alias)
                session.add(row)
                by_alias[key] = row


def set_active_candidate(session: Session, candidate: Candidate) -> None:
    """Guarda el candidato activo en settings."""
    setting = session.get(Setting, "active_candidate_id")
    if setting is None:
        session.add(Setting(key="active_candidate_id", value={"id": candidate.id}))
    else:
        setting.value = {"id": candidate.id}


def get_or_create_candidate(session: Session) -> Candidate:
    """Devuelve el candidato activo; crea uno vacío para el primer arranque."""
    setting = session.get(Setting, "active_candidate_id")
    if setting is not None:
        candidate_id = str(setting.value.get("id", ""))
        candidate = session.get(Candidate, candidate_id) if candidate_id else None
        if candidate is not None:
            return candidate

    candidate = session.scalars(select(Candidate).order_by(Candidate.created_at)).first()
    if candidate is not None:
        set_active_candidate(session, candidate)
        return candidate

    candidate = Candidate()
    session.add(candidate)
    session.flush()
    _seed_candidate_structure(session, candidate)
    set_active_candidate(session, candidate)
    return candidate


def _seed_candidate_structure(session: Session, candidate: Candidate) -> None:
    pref = CandidatePreference(
        candidate_id=candidate.id,
        target_titles=[
            "AI Product Engineer",
            "Full Stack Developer",
            "AI-assisted Developer",
            "Google Ads / SEM Specialist",
            "Landing Page Developer",
        ],
        locations=["Argentina", "LatAm", "Remote"],
        work_modes=["remote", "hybrid"],
        languages=["es", "en"],
        exclusions=["on-site outside Argentina", "fluent English required", "pure sales"],
    )
    session.add(pref)


def create_candidate(session: Session, *, full_name: str = "", headline: str = "") -> Candidate:
    """Crea un candidato nuevo, sin copiar datos personales de otro."""
    candidate = Candidate(full_name=full_name.strip()[:200], headline=headline.strip()[:300])
    session.add(candidate)
    session.flush()
    _seed_candidate_structure(session, candidate)
    _seed_answers(session, candidate)
    _seed_searches(session, candidate)
    set_active_candidate(session, candidate)
    return candidate


def _seed_answers(session: Session, candidate: Candidate) -> None:
    existing = {
        row.key: row
        for row in session.scalars(
            select(AnswerBank).where(AnswerBank.candidate_id == candidate.id)
        )
    }
    for key, pattern in DEFAULT_ANSWERS:
        row = existing.get(key)
        if row is None:
            session.add(
                AnswerBank(
                    candidate_id=candidate.id,
                    key=key,
                    question_pattern=pattern,
                    answer="",
                    verified=False,
                    notes="Completar y verificar en la UI.",
                )
            )


def _seed_searches(session: Session, candidate: Candidate) -> None:
    existing = {
        row.name
        for row in session.scalars(
            select(SearchProfile).where(SearchProfile.candidate_id == candidate.id)
        )
    }
    for data in DEFAULT_SEARCHES:
        if data["name"] in existing:
            continue
        tracks_raw = data.get("tracks")
        tracks = [str(item) for item in tracks_raw] if isinstance(tracks_raw, list) else []
        session.add(
            SearchProfile(
                candidate_id=candidate.id,
                name=str(data["name"]),
                keywords=str(data["keywords"]),
                location="Argentina",
                easy_apply=True,
                date_posted="past_week",
                work_type="remote",
                job_type="full_time",
                max_pages=1,
                min_score=60,
                tracks=tracks,
                enabled=True,
            )
        )


def seed_defaults(session: Session) -> Candidate:
    """Crea catálogos, respuestas iniciales y búsquedas de ejemplo."""
    seed_skills(session)
    candidate = get_or_create_candidate(session)
    _seed_answers(session, candidate)
    _seed_searches(session, candidate)
    return candidate


def main() -> None:
    settings = get_settings()
    init_db(settings)
    with session_scope(settings) as session:
        seed_defaults(session)
    print(f"Seed completado en {settings.database_path}")


if __name__ == "__main__":
    main()
