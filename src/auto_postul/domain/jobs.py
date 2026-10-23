"""Normalización de ofertas provenientes del MCP o de Gemini."""

from __future__ import annotations

import re
from typing import Any

from auto_postul.domain.schemas import ParsedJob
from auto_postul.domain.skills import detect_skills

DESCRIPTION_HEADINGS = (
    "about the job",
    "acerca del empleo",
    "descripción del puesto",
    "descripcion del puesto",
    "job description",
    "descripción",
)
REQUIREMENT_HEADINGS = (
    "requirements",
    "requisitos",
    "qualifications",
    "calificaciones",
    "what you bring",
    "what we expect",
)
BENEFIT_HEADINGS = ("benefits", "beneficios", "about us", "sobre nosotros", "why join")
SENIORITY_MARKERS = {
    "senior": "senior",
    "sr": "senior",
    "ssr": "semi_senior",
    "semi senior": "semi_senior",
    "junior": "junior",
    "lead": "lead",
    "principal": "principal",
    "staff": "staff",
    "trainee": "trainee",
}
FAMILY_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "automation_mcp",
        ("mcp", "automation engineer", "agentes de ia", "ai agents", "automatización con ia"),
    ),
    (
        "google_ads_sem",
        ("google ads", "sem", "search ads", "ppc", "adwords", "performance marketing"),
    ),
    (
        "analytics_measurement",
        ("ga4", "google analytics", "gtm", "tag manager", "hotjar", "clarity", "analytics"),
    ),
    (
        "seo_landing_cro",
        ("seo", "landing page", "cro", "conversion", "search console", "core web vitals"),
    ),
    (
        "ai_product_engineering",
        ("ai product", "product engineer", "prompt engineer", "llm", "vibecoder", "ai engineer"),
    ),
    (
        "ai_assisted_development",
        ("ai-assisted", "asistido por ia", "claude code", "copilot", "cursor", "opencode"),
    ),
    (
        "full_stack",
        ("full stack", "fullstack", "frontend", "backend", "react", "next.js", "node.js"),
    ),
    (
        "technical_product_growth",
        ("growth", "producto", "product manager", "technical product"),
    ),
)


def _clean_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _find_index(lines: list[str], headings: tuple[str, ...], start: int = 0) -> int:
    for index in range(start, len(lines)):
        lowered = lines[index].casefold().strip(" :")
        if any(heading in lowered for heading in headings):
            return index
    return -1


def _section(
    lines: list[str], start_headings: tuple[str, ...], end_headings: tuple[str, ...]
) -> str:
    start = _find_index(lines, start_headings)
    if start == -1:
        return ""
    end = len(lines)
    for index in range(start + 1, len(lines)):
        if any(heading in lines[index].casefold() for heading in end_headings):
            end = index
            break
    return "\n".join(lines[start + 1 : end]).strip()


def detect_apply_type(payload: dict[str, Any]) -> str:
    apply_data = payload.get("apply")
    if isinstance(apply_data, dict):
        value = str(apply_data.get("type", "")).strip()
        if value:
            return value
    return "unknown"


def classify_family(title: str, description: str) -> str:
    text = f"{title} {description[:8000]}".casefold()
    for family, markers in FAMILY_RULES:
        if any(marker in text for marker in markers):
            return family
    return "general"


def detect_work_mode(text: str) -> str:
    folded = text.casefold()
    if any(marker in folded for marker in ("remote", "remoto", "teletrabajo", "home office")):
        if any(marker in folded for marker in ("hybrid", "híbrido", "hibrido")):
            return "hybrid"
        return "remote"
    if any(marker in folded for marker in ("hybrid", "híbrido", "hibrido")):
        return "hybrid"
    if any(marker in folded for marker in ("on-site", "onsite", "presencial")):
        return "on_site"
    return "unknown"


def detect_seniority(title: str) -> str:
    folded = title.casefold()
    for marker, value in SENIORITY_MARKERS.items():
        if re.search(rf"\b{re.escape(marker)}\b", folded):
            return value
    return ""


def detect_salary(text: str) -> tuple[float | None, float | None, str]:
    match = re.search(
        r"(?:USD|US\$|\$)\s*(\d{1,3}(?:[.,]\d{3})*|\d{2,6})\s*(?:-|a|–)\s*(?:USD|US\$|\$)?\s*(\d{1,3}(?:[.,]\d{3})*|\d{2,6})",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None, None, ""
    low = _number(match.group(1))
    high = _number(match.group(2))
    return low, high, "USD"


def _number(value: str) -> float:
    return float(value.replace(".", "").replace(",", ""))


def parse_job_payload(
    payload: dict[str, Any],
    external_id: str,
    url: str,
    gemini_job: ParsedJob | None = None,
) -> ParsedJob:
    """Convierte la respuesta cruda del MCP en una oferta normalizada."""
    sections = payload.get("sections")
    section_text = ""
    if isinstance(sections, dict):
        section_text = str(sections.get("job_posting") or sections.get("search_results") or "")
    if not section_text:
        section_text = str(payload.get("text") or "")

    if gemini_job is not None:
        gemini_job.external_id = external_id
        gemini_job.url = url
        gemini_job.raw_text = section_text
        gemini_job.apply_type = detect_apply_type(payload) or gemini_job.apply_type
        gemini_job.job_family = gemini_job.job_family or classify_family(
            gemini_job.title, gemini_job.description
        )
        return gemini_job

    lines = _clean_lines(section_text)
    title = lines[0] if lines else ""
    company = lines[1] if len(lines) > 1 else ""
    location = lines[2] if len(lines) > 2 else ""

    description = _section(
        lines,
        DESCRIPTION_HEADINGS,
        ("similar jobs", "empleos similares", "people also viewed", "benefits", "beneficios"),
    )
    if not description:
        description = section_text
    requirements = _section(lines, REQUIREMENT_HEADINGS, BENEFIT_HEADINGS)

    skills_found = [skill.slug for skill in detect_skills(section_text)]
    required_found = [skill.slug for skill in detect_skills(requirements)] if requirements else []
    if not required_found:
        required_found = skills_found[:5]

    salary_min, salary_max, currency = detect_salary(section_text)
    apply_type = detect_apply_type(payload)

    return ParsedJob(
        external_id=external_id,
        url=url,
        title=title[:300],
        company=company[:240],
        location=location[:240],
        work_mode=detect_work_mode(section_text),
        employment_type="",
        seniority=detect_seniority(title),
        salary_min=salary_min,
        salary_max=salary_max,
        salary_currency=currency,
        description=description[:20000],
        requirements=requirements[:12000],
        apply_type=apply_type,
        job_family=classify_family(title, description),
        skills=skills_found,
        required_skills=required_found,
        raw_text=section_text,
        raw_payload=payload,
    )


def job_skill_tuples(parsed: ParsedJob) -> list[tuple[str, str, str]]:
    """Devuelve (slug, nombre, tipo) listo para persistir y puntuar."""
    from auto_postul.domain.skills import SKILL_BY_SLUG

    result: list[tuple[str, str, str]] = []
    for slug in parsed.required_skills:
        skill = SKILL_BY_SLUG.get(slug)
        if skill:
            result.append((slug, skill.name, "required"))
    for slug in parsed.skills:
        if slug in parsed.required_skills:
            continue
        skill = SKILL_BY_SLUG.get(slug)
        if skill:
            result.append((slug, skill.name, "nice"))
    return result
