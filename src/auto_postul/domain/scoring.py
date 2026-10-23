"""Rúbrica explicable de afinidad CV–oferta.

Gemini puede extraer requisitos y evidencia, pero el número final se calcula
aquí. Así el panel siempre puede mostrar por qué una oferta puntúa como puntúa.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from auto_postul.domain.schemas import ScoreComponent, ScoreResult

WEIGHTS: dict[str, int] = {
    "required_skills": 30,
    "nice_skills": 15,
    "role_fit": 15,
    "domain_fit": 10,
    "location_fit": 10,
    "language_fit": 5,
    "experience_fit": 5,
    "education_fit": 5,
    "application_ease": 5,
}


@dataclass(slots=True)
class CandidateSnapshot:
    skills: dict[str, str] = field(default_factory=dict)
    target_titles: list[str] = field(default_factory=list)
    tracks: list[str] = field(default_factory=list)
    location: str = ""
    work_modes: list[str] = field(default_factory=list)
    years_experience: float = 0.0
    english_level: str = ""
    has_degree: bool = False
    degree_in_progress: bool = False
    headline: str = ""


@dataclass(slots=True)
class JobSnapshot:
    title: str = ""
    company: str = ""
    location: str = ""
    work_mode: str = "unknown"
    description: str = ""
    requirements: str = ""
    job_family: str = ""
    apply_type: str = "unknown"


def _fold(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(char for char in normalized if not unicodedata.combining(char)).casefold()


def _tokens(value: str) -> set[str]:
    stop = {
        "de",
        "del",
        "la",
        "las",
        "el",
        "los",
        "y",
        "o",
        "para",
        "con",
        "en",
        "a",
        "al",
        "un",
        "una",
        "the",
        "and",
        "or",
        "for",
        "with",
        "of",
        "to",
        "in",
    }
    return {
        token
        for token in re.findall(r"[a-z0-9+#.]+", _fold(value))
        if len(token) > 2 and token not in stop
    }


def _ratio(part: int, total: int, default: float = 0.0) -> float:
    if total <= 0:
        return default
    return max(0.0, min(1.0, part / total))


def _required_years(text: str) -> float:
    match = re.search(r"(\d{1,2})\s*\+?\s*(?:years?|años?)", _fold(text), re.IGNORECASE)
    return float(match.group(1)) if match else 0.0


def _needs_fluent_english(text: str) -> bool:
    folded = _fold(text)
    markers = (
        "fluent english",
        "english fluency",
        "advanced english",
        "ingles fluido",
        "ingles avanzado",
        "bilingual",
        "english b2",
        "english c1",
        "english c2",
        "ingles b2",
        "ingles intermedio",
        "intermediate english",
    )
    return any(marker in folded for marker in markers)


def _needs_degree(text: str) -> bool:
    folded = _fold(text)
    markers = (
        "bachelor",
        "degree in",
        "titulo universitario",
        "titulo de grado",
        "ingenieria en sistemas",
        "licenciatura",
        "computer science degree",
    )
    return any(marker in folded for marker in markers)


def band_for(total: int) -> str:
    if total >= 90:
        return "muy_alta"
    if total >= 75:
        return "alta"
    if total >= 60:
        return "media"
    if total >= 40:
        return "media_baja"
    return "baja"


def score_job(
    candidate: CandidateSnapshot,
    job: JobSnapshot,
    job_skills: list[tuple[str, str, str]],
    search_min_score: int = 0,
) -> ScoreResult:
    """Calcula 0–100 y devuelve componentes, evidencia y riesgos."""
    candidate_skills = set(candidate.skills)
    required = [(slug, name) for slug, name, kind in job_skills if kind == "required"]
    nice = [(slug, name) for slug, name, kind in job_skills if kind == "nice"]

    required_matches = [(slug, name) for slug, name in required if slug in candidate_skills]
    required_missing = [(slug, name) for slug, name in required if slug not in candidate_skills]
    nice_matches = [(slug, name) for slug, name in nice if slug in candidate_skills]

    if required:
        required_raw = _ratio(len(required_matches), len(required), default=0.0)
    else:
        overlap = len(candidate_skills.intersection({slug for slug, _ in nice}))
        required_raw = 0.7 if overlap else 0.5

    nice_raw = _ratio(len(nice_matches), len(nice), default=1.0)

    title_tokens = _tokens(job.title)
    target_tokens = _tokens(" ".join([*candidate.target_titles, candidate.headline]))
    role_raw = _ratio(len(title_tokens & target_tokens), len(title_tokens), default=0.4)
    if not title_tokens:
        role_raw = 0.4

    if job.job_family and job.job_family in candidate.tracks:
        domain_raw = 1.0
    elif job.job_family in ("", "general"):
        domain_raw = 0.6
    else:
        domain_raw = 0.4

    location_raw = _location_fit(candidate, job)
    language_raw = _language_fit(candidate, job)
    experience_raw = _experience_fit(candidate, job)
    education_raw = _education_fit(candidate, job)
    ease_raw = {
        "easy_apply": 1.0,
        "external": 0.4,
        "applied": 0.0,
        "closed": 0.0,
        "unknown": 0.5,
    }.get(job.apply_type, 0.5)

    raw_values: dict[str, tuple[float, str]] = {
        "required_skills": (
            required_raw,
            f"{len(required_matches)}/{len(required)} obligatorias cubiertas"
            if required
            else "La oferta no declara skills obligatorias",
        ),
        "nice_skills": (
            nice_raw,
            f"{len(nice_matches)}/{len(nice)} deseables cubiertas" if nice else "Sin deseables",
        ),
        "role_fit": (role_raw, f"Título: {job.title or 'sin título'}"),
        "domain_fit": (domain_raw, f"Familia: {job.job_family or 'general'}"),
        "location_fit": (location_raw, f"Ubicación/modalidad: {job.location or job.work_mode}"),
        "language_fit": (language_raw, f"Nivel declarado: {candidate.english_level or 'sin dato'}"),
        "experience_fit": (
            experience_raw,
            f"{candidate.years_experience:.0f} años vs. requisito detectado",
        ),
        "education_fit": (education_raw, "Formación declarada en el CV"),
        "application_ease": (ease_raw, f"Tipo de postulación: {job.apply_type}"),
    }

    components: list[ScoreComponent] = []
    for key, weight in WEIGHTS.items():
        raw, evidence = raw_values[key]
        components.append(
            ScoreComponent(
                key=key,
                label=_label(key),
                weight=weight,
                raw=raw,
                points=weight * raw,
                evidence=evidence,
            )
        )

    total = round(sum(component.points for component in components))
    risks: list[str] = []
    cap = 100

    if required and len(required_missing) >= max(1, len(required) // 2):
        cap = min(cap, 50)
        risks.append("Faltan varias skills obligatorias declaradas por la oferta.")
    if _needs_fluent_english(job.description + " " + job.requirements):
        cap = min(cap, 55)
        risks.append("La oferta parece exigir inglés fluido y el CV declara nivel básico.")
    if job.work_mode == "on_site" and not _is_argentina(job.location):
        cap = min(cap, 40)
        risks.append("Presencialidad fuera de Argentina.")
    if job.apply_type in ("applied", "closed"):
        cap = min(cap, 20)
        risks.append("La oferta ya fue aplicada o está cerrada.")
    if job.apply_type == "external":
        risks.append("No es Easy Apply: el envío automático no está habilitado.")

    total = min(total, cap)
    if total < search_min_score:
        risks.append(f"Queda por debajo del umbral configurado ({search_min_score}).")

    matched = [name for _, name in required_matches + nice_matches]
    missing = [name for _, name in required_missing]
    summary = _summary(total, matched, missing, risks)
    return ScoreResult(
        total=total,
        band=band_for(total),
        components=components,
        matched_skills=matched,
        missing_skills=missing,
        risks=risks,
        summary=summary,
    )


def _label(key: str) -> str:
    return {
        "required_skills": "Skills obligatorias",
        "nice_skills": "Skills deseables",
        "role_fit": "Rol y seniority",
        "domain_fit": "Dominio",
        "location_fit": "Ubicación y modalidad",
        "language_fit": "Idioma",
        "experience_fit": "Experiencia",
        "education_fit": "Formación",
        "application_ease": "Facilidad de postulación",
    }[key]


def _location_fit(candidate: CandidateSnapshot, job: JobSnapshot) -> float:
    mode = job.work_mode
    if mode == "remote":
        return 1.0
    if mode == "hybrid":
        return 0.8 if "hybrid" in candidate.work_modes or "remote" in candidate.work_modes else 0.5
    if mode == "on_site":
        if _is_argentina(job.location) or _is_argentina(candidate.location):
            return 0.75
        return 0.15
    return 0.6


def _language_fit(candidate: CandidateSnapshot, job: JobSnapshot) -> float:
    text = f"{job.description} {job.requirements}"
    if not _needs_fluent_english(text):
        return 1.0
    level = _fold(candidate.english_level)
    if any(marker in level for marker in ("a1", "a2", "basico", "básico")):
        return 0.15
    if any(marker in level for marker in ("b1", "b2", "intermedio")):
        return 0.55
    return 1.0


def _experience_fit(candidate: CandidateSnapshot, job: JobSnapshot) -> float:
    required = _required_years(f"{job.description} {job.requirements}")
    if required <= 0:
        return 1.0
    if candidate.years_experience >= required:
        return 1.0
    return max(0.1, candidate.years_experience / required)


def _education_fit(candidate: CandidateSnapshot, job: JobSnapshot) -> float:
    if not _needs_degree(f"{job.description} {job.requirements}"):
        return 1.0
    if candidate.has_degree:
        return 1.0
    if candidate.degree_in_progress:
        return 0.7
    return 0.45


def _is_argentina(value: str) -> bool:
    return "argentina" in _fold(value) or "latam" in _fold(value) or "latinoamerica" in _fold(value)


def _summary(total: int, matched: list[str], missing: list[str], risks: list[str]) -> str:
    parts = [f"Afinidad {total}/100."]
    if matched:
        parts.append("Coincidencias: " + ", ".join(matched[:4]) + ".")
    if missing:
        parts.append("Faltantes: " + ", ".join(missing[:3]) + ".")
    if risks:
        parts.append("Atención: " + " ".join(risks[:2]))
    return " ".join(parts)
