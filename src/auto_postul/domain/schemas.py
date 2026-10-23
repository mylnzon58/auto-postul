"""Estructuras de dominio compartidas entre casos de uso y adaptadores."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class CvExperience:
    title: str = ""
    company: str = ""
    start_date: str = ""
    end_date: str = ""
    is_current: bool = False
    description: str = ""


@dataclass(slots=True)
class CvEducation:
    institution: str = ""
    degree: str = ""
    field: str = ""
    start_date: str = ""
    end_date: str = ""
    status: str = ""
    description: str = ""


@dataclass(slots=True)
class CvData:
    full_name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    headline: str = ""
    summary: str = ""
    linkedin_url: str = ""
    github_url: str = ""
    portfolio_url: str = ""
    years_experience: float = 0.0
    english_level: str = ""
    skills: list[str] = field(default_factory=list)
    experiences: list[CvExperience] = field(default_factory=list)
    education: list[CvEducation] = field(default_factory=list)
    languages: list[tuple[str, str]] = field(default_factory=list)
    certifications: list[str] = field(default_factory=list)
    raw_text: str = ""


@dataclass(slots=True)
class ParsedJob:
    external_id: str
    url: str
    title: str = ""
    company: str = ""
    location: str = ""
    work_mode: str = "unknown"
    employment_type: str = ""
    seniority: str = ""
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str = ""
    description: str = ""
    requirements: str = ""
    apply_type: str = "unknown"
    job_family: str = ""
    skills: list[str] = field(default_factory=list)
    required_skills: list[str] = field(default_factory=list)
    raw_text: str = ""
    raw_payload: dict[str, Any] = field(default_factory=dict)
    posted_at: datetime | None = None


@dataclass(slots=True)
class ScoreComponent:
    key: str
    label: str
    weight: int
    raw: float
    points: float
    evidence: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "weight": self.weight,
            "raw": round(self.raw, 4),
            "points": round(self.points, 2),
            "evidence": self.evidence,
        }


@dataclass(slots=True)
class ScoreResult:
    total: int
    band: str
    components: list[ScoreComponent]
    matched_skills: list[str]
    missing_skills: list[str]
    risks: list[str]
    summary: str
    rubric_version: str = "1.0"

    def as_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "band": self.band,
            "components": [component.as_dict() for component in self.components],
            "matched_skills": self.matched_skills,
            "missing_skills": self.missing_skills,
            "risks": self.risks,
            "summary": self.summary,
            "rubric_version": self.rubric_version,
        }


@dataclass(slots=True)
class FormField:
    key: str
    label: str
    field_type: str
    required: bool = False
    value: str = ""
    options: list[str] = field(default_factory=list)
    step: int = 1
    source: str = ""
    status: str = "pending"
    confidence: float = 0.0


@dataclass(slots=True)
class PrepareResult:
    status: str
    fields: list[FormField]
    message: str = ""
    screenshot: str = ""
    review_url: str = ""
    browser_state: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SubmitResult:
    status: str
    message: str = ""
    screenshot: str = ""
    confirmed: bool = False
    browser_state: dict[str, Any] = field(default_factory=dict)
