"""Extracción local y heurísticas para convertir un CV en datos revisables."""

from __future__ import annotations

import re
from pathlib import Path

from pypdf import PdfReader

from auto_postul.domain.schemas import CvData, CvEducation, CvExperience
from auto_postul.domain.skills import detect_skills

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
PHONE_RE = re.compile(r"(?:\+?\d[\d\s().-]{7,}\d)")
LINKEDIN_RE = re.compile(r"(?:https?://)?(?:www\.)?linkedin\.com/in/[\w-]+", re.IGNORECASE)
GITHUB_RE = re.compile(r"(?:https?://)?(?:www\.)?github\.com/[\w-]+", re.IGNORECASE)
YEARS_RE = re.compile(r"(?:m[áa]s de\s+)?(\d{1,2})\s*(?:\+)?\s*a[ñn]os", re.IGNORECASE)
DATE_RANGE_RE = re.compile(
    r"(?P<start>\d{2}/\d{4}|\d{4})\s*[–\-]\s*(?P<end>Actualidad|\d{2}/\d{4}|\d{4})",
    re.IGNORECASE,
)
SECTION_HEADINGS = {
    "perfil profesional",
    "fortalezas clave",
    "experiencia profesional",
    "productos y proyectos destacados",
    "ventas, negocio y coaching técnico",
    "competencias técnicas",
    "ampliación de competencias — marketing, conversión y desarrollo asistido",
    "formación y certificaciones",
    "idiomas",
}


def extract_pdf_text(path: Path) -> str:
    """Extrae texto de un PDF. Lanza un error legible si no hay texto."""
    reader = PdfReader(str(path))
    pages = [page.extract_text() or "" for page in reader.pages]
    text = "\n".join(pages).strip()
    if not text:
        raise ValueError(
            "El PDF no contiene texto extraíble. Probá con un PDF digital o cargá el texto manualmente."
        )
    return text


def _clean_line(line: str) -> str:
    return line.replace("\uf0b7", " ").replace("\u2022", " ").strip(" \t-")


def _section(text: str, start: str, end: str | None) -> str:
    lowered = text.casefold()
    start_index = lowered.find(start.casefold())
    if start_index == -1:
        return ""
    start_index += len(start)
    end_index = len(text)
    if end:
        candidate = lowered.find(end.casefold(), start_index)
        if candidate != -1:
            end_index = candidate
    return text[start_index:end_index].strip()


def _lines_between(text: str, start: str, end: str | None) -> list[str]:
    raw = _section(text, start, end)
    return [_clean_line(line) for line in raw.splitlines() if _clean_line(line)]


def _parse_experiences(text: str) -> list[CvExperience]:
    raw = _section(text, "EXPERIENCIA PROFESIONAL", "PRODUCTOS Y PROYECTOS DESTACADOS")
    if not raw:
        return []
    lines = [_clean_line(line) for line in raw.splitlines() if _clean_line(line)]

    # En este CV cada bloque empieza con cargo y sigue con "Empresa | fechas".
    starts = [
        index
        for index in range(len(lines) - 1)
        if "|" in lines[index + 1] and "|" not in lines[index]
    ]
    experiences: list[CvExperience] = []
    for position, start in enumerate(starts):
        title = lines[start]
        company_line = lines[start + 1]
        company = company_line.split("|", 1)[0].strip()
        match = DATE_RANGE_RE.search(company_line)
        end = starts[position + 1] if position + 1 < len(starts) else len(lines)
        description = "\n".join(lines[start + 2 : end]).strip()
        current_end = match.group("end") if match else ""
        experiences.append(
            CvExperience(
                title=title,
                company=company,
                start_date=match.group("start") if match else "",
                end_date="" if current_end.casefold() == "actualidad" else current_end,
                is_current=current_end.casefold() == "actualidad",
                description=description,
            )
        )
    return experiences_clean(experiences)


def experiences_clean(experiences: list[CvExperience]) -> list[CvExperience]:
    """Descarta ruido de encabezados y recorta descripciones enormes."""
    cleaned: list[CvExperience] = []
    seen: set[tuple[str, str]] = set()
    for item in experiences:
        title = item.title.strip()
        company = item.company.strip()
        if not title and not company:
            continue
        if title.casefold() in SECTION_HEADINGS:
            continue
        key = (title.casefold(), company.casefold())
        if key in seen:
            continue
        seen.add(key)
        item.description = item.description[:4000]
        cleaned.append(item)
    return cleaned


def _parse_education(text: str) -> tuple[list[CvEducation], list[str]]:
    lines = _lines_between(text, "FORMACIÓN Y CERTIFICACIONES", "IDIOMAS")
    education: list[CvEducation] = []
    certifications: list[str] = []
    for line in lines:
        if not line:
            continue
        if any(
            word in line.casefold() for word in ("ingeniería", "bachiller", "análisis de sistemas")
        ):
            education.append(CvEducation(degree=line, status="declarado en CV"))
        elif any(
            word in line.casefold() for word in ("curso", "certificaci", "semana", "apps móviles")
        ):
            certifications.append(line)
        else:
            certifications.append(line)
    return education, certifications


def _parse_languages(text: str) -> list[tuple[str, str]]:
    section = _section(text, "IDIOMAS", None)
    if not section:
        return []
    languages: list[tuple[str, str]] = []
    for chunk in re.split(r"[·|]", section):
        if ":" in chunk:
            name, level = chunk.split(":", 1)
            languages.append((_clean_line(name), _clean_line(level)))
    return [(name, level) for name, level in languages if name and level]


def parse_cv_text(text: str) -> CvData:
    """Heurística conservadora; la UI permite corregir todos los campos."""
    lines = [_clean_line(line) for line in text.splitlines() if _clean_line(line)]
    first = lines[0] if lines else ""
    headline = lines[1] if len(lines) > 1 else ""
    location = ""
    for line in lines[:8]:
        if "argentina" in line.casefold() or "remoto" in line.casefold():
            location = line
            break

    email = EMAIL_RE.search(text)
    phone = PHONE_RE.search(text)
    linkedin = LINKEDIN_RE.search(text)
    github = GITHUB_RE.search(text)
    years = YEARS_RE.search(text)
    english_match = re.search(r"Ingl[ée]s\s*:\s*([^\n·|]+)", text, re.IGNORECASE)

    summary = _section(text, "PERFIL PROFESIONAL", "FORTALEZAS CLAVE")
    if not summary:
        summary = "\n".join(lines[2:8])

    skills = [skill.slug for skill in detect_skills(text)]
    education, certifications = _parse_education(text)
    experiences = _parse_experiences(text)
    languages = _parse_languages(text)

    return CvData(
        full_name=first[:200],
        email=email.group(0) if email else "",
        phone=phone.group(0).strip() if phone else "",
        location=location[:240],
        headline=headline[:300],
        summary=summary[:6000],
        linkedin_url=f"https://{linkedin.group(0).removeprefix('https://').removeprefix('http://')}"
        if linkedin
        else "",
        github_url=f"https://{github.group(0).removeprefix('https://').removeprefix('http://')}"
        if github
        else "",
        years_experience=float(years.group(1)) if years else 0.0,
        english_level=_clean_line(english_match.group(1)) if english_match else "",
        skills=skills,
        experiences=experiences,
        education=education,
        languages=languages,
        certifications=certifications,
        raw_text=text,
    )
