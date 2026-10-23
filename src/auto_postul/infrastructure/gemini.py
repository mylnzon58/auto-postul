"""Adaptador de Google AI Studio / Gemini con salida estructurada y conservadora."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from auto_postul.config import Settings
from auto_postul.domain.schemas import CvData, CvEducation, CvExperience, ParsedJob
from auto_postul.domain.skills import canonical_slug, detect_skills

logger = logging.getLogger(__name__)


CV_PROMPT = """Eres un extractor de datos de CV. Devuelve SOLO JSON válido.
No inventes datos. Si un campo no aparece, usa "" o [].
Usa español en los textos. Devuelve exactamente este esquema:
{
  "full_name": "", "email": "", "phone": "", "location": "", "headline": "",
  "summary": "", "linkedin_url": "", "github_url": "", "portfolio_url": "",
  "years_experience": 0, "english_level": "",
  "skills": ["slug de skill"],
  "experiences": [{"title":"","company":"","start_date":"","end_date":"","is_current":false,"description":""}],
  "education": [{"institution":"","degree":"","field":"","start_date":"","end_date":"","status":"","description":""}],
  "languages": [["Español","Nativo"]],
  "certifications": [""]
}
Para skills usa slugs canónicos cuando puedas: python, javascript, typescript, php, nodejs,
react, nextjs, sql, postgresql, supabase, docker, git, mcp, llm, prompt-engineering,
google-ads, google-ads-search, seo, ga4, gtm, hotjar, clarity, landing-pages, cro,
core-web-vitals, owasp, multi-tenant, rls. No agregues skills que no estén en el CV.
"""

JOB_PROMPT = """Eres un analista de ofertas laborales. Devuelve SOLO JSON válido.
No inventes requisitos. Extrae solo lo que aparece en el texto.
Esquema:
{
  "title":"", "company":"", "location":"", "work_mode":"remote|hybrid|on_site|unknown",
  "employment_type":"", "seniority":"", "salary_min":null, "salary_max":null,
  "salary_currency":"", "description":"", "requirements":"",
  "skills":["slug"], "required_skills":["slug"], "job_family":""
}
Familias válidas: ai_product_engineering, ai_assisted_development, full_stack,
google_ads_sem, seo_landing_cro, analytics_measurement, automation_mcp,
technical_product_growth, general.
"""


class GeminiService:
    """Servicio opcional: si no hay clave, la app sigue funcionando con reglas."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._client: Any | None = None
        self._disabled_reason = ""

    @property
    def available(self) -> bool:
        return self.settings.gemini_enabled and not self._disabled_reason

    def _disable_if_fatal(self, exc: Exception) -> None:
        message = str(exc).casefold()
        if "leaked" in message or "permission_denied" in message:
            self._disabled_reason = "La API key de Gemini fue rechazada."
            logger.error("Gemini deshabilitado en esta ejecución: %s", exc)

    def _get_client(self) -> Any:
        if not self.available:
            raise RuntimeError("Gemini no está configurado.")
        if self._client is None:
            from google import genai

            self._client = genai.Client(api_key=self.settings.gemini_api_key)
        return self._client

    async def _generate(self, prompt: str, payload: bytes | None = None, mime: str = "") -> str:
        client = self._get_client()
        contents: list[Any] = [prompt]
        if payload is not None:
            from google.genai import types

            contents.append(
                types.Part.from_bytes(data=payload, mime_type=mime or "application/pdf")
            )
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                response = await client.aio.models.generate_content(
                    model=self.settings.gemini_model,
                    contents=contents,
                    config={"response_mime_type": "application/json", "temperature": 0.0},
                )
                return response.text or ""
            except Exception as exc:
                last_error = exc
                if not _is_transient(exc) or attempt == 2:
                    raise
                await asyncio.sleep(2**attempt)
        raise last_error or RuntimeError("Gemini no respondió.")

    async def extract_cv(self, text: str, pdf_bytes: bytes | None = None) -> CvData | None:
        """Extrae un CV. Si falla, el llamador usa la heurística local."""
        if not self.available:
            return None
        try:
            raw = await self._generate(CV_PROMPT + "\n\nCV:\n" + text[:30000], pdf_bytes)
            data = _loads(raw)
            return _cv_from_dict(data, text)
        except Exception as exc:
            self._disable_if_fatal(exc)
            logger.warning("Gemini no pudo estructurar el CV: %s", exc)
            return None

    async def extract_job(self, text: str, external_id: str, url: str) -> ParsedJob | None:
        """Extrae una oferta. Si falla, el llamador usa el parser local."""
        if not self.available:
            return None
        try:
            raw = await self._generate(JOB_PROMPT + "\n\nOFERTA:\n" + text[:30000])
            data = _loads(raw)
            return _job_from_dict(data, text, external_id, url)
        except Exception as exc:
            self._disable_if_fatal(exc)
            logger.warning("Gemini no pudo estructurar la oferta: %s", exc)
            return None

    async def draft_answer(self, question: str, candidate_facts: str) -> str:
        """Redacta una respuesta breve usando solo hechos verificados."""
        if not self.available:
            return ""
        prompt = (
            "Responde la pregunta de postulación en primera persona, en español, "
            "en 2 o 3 frases. Usa SOLO los hechos del perfil. Si falta información, "
            "responde exactamente: NECESITO_DATO. No inventes.\n\n"
            f"PERFIL:\n{candidate_facts}\n\nPREGUNTA:\n{question}"
        )
        try:
            client = self._get_client()
            response = await client.aio.models.generate_content(
                model=self.settings.gemini_model,
                contents=prompt,
                config={"temperature": 0.2},
            )
            return (response.text or "").strip()
        except Exception as exc:
            self._disable_if_fatal(exc)
            logger.warning("Gemini no pudo redactar la respuesta: %s", exc)
            return ""


def _is_transient(exc: Exception) -> bool:
    message = str(exc).casefold()
    return any(
        marker in message
        for marker in ("unavailable", "resource_exhausted", "429", "503", "high demand", "timeout")
    )


def _loads(raw: str) -> dict[str, Any]:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.removeprefix("json").strip()
    parsed = json.loads(cleaned)
    if not isinstance(parsed, dict):
        raise ValueError("La respuesta no es un objeto JSON.")
    return parsed


def _as_str(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_skills(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    result: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        slug = canonical_slug(value)
        if slug and slug not in result:
            result.append(slug)
    return result


def _cv_from_dict(data: dict[str, Any], source_text: str) -> CvData:
    experiences = []
    for item in data.get("experiences", []) if isinstance(data.get("experiences"), list) else []:
        if not isinstance(item, dict):
            continue
        experiences.append(
            CvExperience(
                title=_as_str(item.get("title")),
                company=_as_str(item.get("company")),
                start_date=_as_str(item.get("start_date")),
                end_date=_as_str(item.get("end_date")),
                is_current=bool(item.get("is_current")),
                description=_as_str(item.get("description")),
            )
        )
    education = []
    for item in data.get("education", []) if isinstance(data.get("education"), list) else []:
        if not isinstance(item, dict):
            continue
        education.append(
            CvEducation(
                institution=_as_str(item.get("institution")),
                degree=_as_str(item.get("degree")),
                field=_as_str(item.get("field")),
                start_date=_as_str(item.get("start_date")),
                end_date=_as_str(item.get("end_date")),
                status=_as_str(item.get("status")),
                description=_as_str(item.get("description")),
            )
        )
    languages = []
    for item in data.get("languages", []) if isinstance(data.get("languages"), list) else []:
        if isinstance(item, list) and len(item) >= 2:
            languages.append((_as_str(item[0]), _as_str(item[1])))
        elif isinstance(item, dict):
            languages.append((_as_str(item.get("name")), _as_str(item.get("level"))))

    skills = _normalize_skills(data.get("skills"))
    if not skills:
        skills = [skill.slug for skill in detect_skills(source_text)]

    return CvData(
        full_name=_as_str(data.get("full_name"))[:200],
        email=_as_str(data.get("email"))[:320],
        phone=_as_str(data.get("phone"))[:80],
        location=_as_str(data.get("location"))[:240],
        headline=_as_str(data.get("headline"))[:300],
        summary=_as_str(data.get("summary"))[:6000],
        linkedin_url=_as_str(data.get("linkedin_url"))[:500],
        github_url=_as_str(data.get("github_url"))[:500],
        portfolio_url=_as_str(data.get("portfolio_url"))[:500],
        years_experience=_as_float(data.get("years_experience")),
        english_level=_as_str(data.get("english_level"))[:40],
        skills=skills,
        experiences=experiences,
        education=education,
        languages=languages,
        certifications=[_as_str(value) for value in data.get("certifications", [])]
        if isinstance(data.get("certifications"), list)
        else [],
        raw_text=source_text,
    )


def _job_from_dict(data: dict[str, Any], source_text: str, external_id: str, url: str) -> ParsedJob:
    skills = _normalize_skills(data.get("skills"))
    required = _normalize_skills(data.get("required_skills")) or skills
    return ParsedJob(
        external_id=external_id,
        url=url,
        title=_as_str(data.get("title"))[:300],
        company=_as_str(data.get("company"))[:240],
        location=_as_str(data.get("location"))[:240],
        work_mode=_as_str(data.get("work_mode")) or "unknown",
        employment_type=_as_str(data.get("employment_type"))[:80],
        seniority=_as_str(data.get("seniority"))[:80],
        salary_min=_as_float(data.get("salary_min")) or None,
        salary_max=_as_float(data.get("salary_max")) or None,
        salary_currency=_as_str(data.get("salary_currency"))[:10],
        description=_as_str(data.get("description"))[:20000],
        requirements=_as_str(data.get("requirements"))[:12000],
        job_family=_as_str(data.get("job_family")) or "general",
        skills=skills,
        required_skills=required,
        raw_text=source_text,
        raw_payload=data,
    )
