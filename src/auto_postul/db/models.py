"""Modelo relacional normalizado de AutoPostul."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from auto_postul.db.base import Base, new_id, utcnow
from auto_postul.domain.enums import (
    ApplicationStatus,
    ApplyType,
    RequirementType,
    TaskKind,
    TaskStatus,
    WorkMode,
)


class Candidate(Base):
    __tablename__ = "candidate"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=new_id)
    full_name: Mapped[str] = mapped_column(String(200), default="")
    email: Mapped[str] = mapped_column(String(320), default="")
    phone: Mapped[str] = mapped_column(String(80), default="")
    location: Mapped[str] = mapped_column(String(240), default="")
    headline: Mapped[str] = mapped_column(String(300), default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    linkedin_url: Mapped[str] = mapped_column(String(500), default="")
    github_url: Mapped[str] = mapped_column(String(500), default="")
    portfolio_url: Mapped[str] = mapped_column(String(500), default="")
    years_experience: Mapped[float] = mapped_column(Float, default=0.0)
    english_level: Mapped[str] = mapped_column(String(40), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class CandidateDocument(Base):
    __tablename__ = "candidate_document"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=new_id)
    candidate_id: Mapped[str] = mapped_column(
        ForeignKey("candidate.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(40), default="cv")
    filename: Mapped[str] = mapped_column(String(300), default="")
    stored_path: Mapped[str] = mapped_column(String(1000), default="")
    sha256: Mapped[str] = mapped_column(String(64), index=True, default="")
    mime_type: Mapped[str] = mapped_column(String(120), default="application/pdf")
    text_content: Mapped[str] = mapped_column(Text, default="")
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CandidatePreference(Base):
    __tablename__ = "candidate_preference"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=new_id)
    candidate_id: Mapped[str] = mapped_column(
        ForeignKey("candidate.id", ondelete="CASCADE"), unique=True
    )
    target_titles: Mapped[list[str]] = mapped_column(JSON, default=list)
    locations: Mapped[list[str]] = mapped_column(JSON, default=list)
    work_modes: Mapped[list[str]] = mapped_column(JSON, default=list)
    languages: Mapped[list[str]] = mapped_column(JSON, default=list)
    exclusions: Mapped[list[str]] = mapped_column(JSON, default=list)
    salary_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    salary_currency: Mapped[str] = mapped_column(String(10), default="USD")
    willing_to_relocate: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class Experience(Base):
    __tablename__ = "experience"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=new_id)
    candidate_id: Mapped[str] = mapped_column(
        ForeignKey("candidate.id", ondelete="CASCADE"), index=True
    )
    company: Mapped[str] = mapped_column(String(240), default="")
    title: Mapped[str] = mapped_column(String(240), default="")
    start_date: Mapped[str] = mapped_column(String(20), default="")
    end_date: Mapped[str] = mapped_column(String(20), default="")
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)
    description: Mapped[str] = mapped_column(Text, default="")
    achievements: Mapped[list[str]] = mapped_column(JSON, default=list)


class Education(Base):
    __tablename__ = "education"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=new_id)
    candidate_id: Mapped[str] = mapped_column(
        ForeignKey("candidate.id", ondelete="CASCADE"), index=True
    )
    institution: Mapped[str] = mapped_column(String(240), default="")
    degree: Mapped[str] = mapped_column(String(240), default="")
    field: Mapped[str] = mapped_column(String(240), default="")
    start_date: Mapped[str] = mapped_column(String(20), default="")
    end_date: Mapped[str] = mapped_column(String(20), default="")
    status: Mapped[str] = mapped_column(String(80), default="")
    description: Mapped[str] = mapped_column(Text, default="")


class Certification(Base):
    __tablename__ = "certification"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=new_id)
    candidate_id: Mapped[str] = mapped_column(
        ForeignKey("candidate.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(300), default="")
    issuer: Mapped[str] = mapped_column(String(240), default="")
    year: Mapped[str] = mapped_column(String(10), default="")
    url: Mapped[str] = mapped_column(String(500), default="")


class Language(Base):
    __tablename__ = "language"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=new_id)
    candidate_id: Mapped[str] = mapped_column(
        ForeignKey("candidate.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(80), default="")
    level: Mapped[str] = mapped_column(String(80), default="")


class Skill(Base):
    __tablename__ = "skill"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=new_id)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160), default="")
    category: Mapped[str] = mapped_column(String(80), default="general")


class SkillAlias(Base):
    __tablename__ = "skill_alias"
    __table_args__ = (UniqueConstraint("alias", name="uq_skill_alias_alias"),)

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=new_id)
    skill_id: Mapped[str] = mapped_column(ForeignKey("skill.id", ondelete="CASCADE"), index=True)
    alias: Mapped[str] = mapped_column(String(160), index=True)


class CandidateSkill(Base):
    __tablename__ = "candidate_skill"
    __table_args__ = (UniqueConstraint("candidate_id", "skill_id", name="uq_candidate_skill"),)

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=new_id)
    candidate_id: Mapped[str] = mapped_column(
        ForeignKey("candidate.id", ondelete="CASCADE"), index=True
    )
    skill_id: Mapped[str] = mapped_column(ForeignKey("skill.id", ondelete="CASCADE"), index=True)
    level: Mapped[str] = mapped_column(String(40), default="")
    years: Mapped[float] = mapped_column(Float, default=0.0)
    evidence: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(40), default="cv")


class SearchProfile(Base):
    __tablename__ = "search_profile"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=new_id)
    candidate_id: Mapped[str] = mapped_column(
        ForeignKey("candidate.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(160), default="")
    keywords: Mapped[str] = mapped_column(String(500), default="")
    location: Mapped[str] = mapped_column(String(240), default="")
    easy_apply: Mapped[bool] = mapped_column(Boolean, default=True)
    date_posted: Mapped[str] = mapped_column(String(40), default="past_week")
    work_type: Mapped[str] = mapped_column(String(40), default="remote")
    job_type: Mapped[str] = mapped_column(String(60), default="full_time")
    experience_level: Mapped[str] = mapped_column(String(60), default="")
    max_pages: Mapped[int] = mapped_column(Integer, default=1)
    min_score: Mapped[int] = mapped_column(Integer, default=0)
    tracks: Mapped[list[str]] = mapped_column(JSON, default=list)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Company(Base):
    __tablename__ = "company"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(240), default="")
    normalized_name: Mapped[str] = mapped_column(String(240), unique=True, index=True)
    linkedin_url: Mapped[str] = mapped_column(String(500), default="")


class JobPosting(Base):
    __tablename__ = "job_posting"
    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_job_source_external"),
        Index("ix_job_created_at", "created_at"),
        Index("ix_job_apply_type", "apply_type"),
    )

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=new_id)
    source: Mapped[str] = mapped_column(String(40), default="linkedin")
    external_id: Mapped[str] = mapped_column(String(80), index=True)
    url: Mapped[str] = mapped_column(String(1000), default="")
    title: Mapped[str] = mapped_column(String(300), default="")
    company_id: Mapped[str | None] = mapped_column(
        ForeignKey("company.id", ondelete="SET NULL"), nullable=True, index=True
    )
    company_name: Mapped[str] = mapped_column(String(240), default="")
    location: Mapped[str] = mapped_column(String(240), default="")
    work_mode: Mapped[str] = mapped_column(String(20), default=WorkMode.UNKNOWN.value)
    employment_type: Mapped[str] = mapped_column(String(80), default="")
    seniority: Mapped[str] = mapped_column(String(80), default="")
    salary_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    salary_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    salary_currency: Mapped[str] = mapped_column(String(10), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    requirements: Mapped[str] = mapped_column(Text, default="")
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    apply_type: Mapped[str] = mapped_column(String(20), default=ApplyType.UNKNOWN.value)
    job_family: Mapped[str] = mapped_column(String(80), default="")
    raw_text: Mapped[str] = mapped_column(Text, default="")
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    fingerprint: Mapped[str] = mapped_column(String(64), index=True, default="")
    search_profile_id: Mapped[str | None] = mapped_column(
        ForeignKey("search_profile.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class JobSkill(Base):
    __tablename__ = "job_skill"
    __table_args__ = (UniqueConstraint("job_id", "skill_id", name="uq_job_skill"),)

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=new_id)
    job_id: Mapped[str] = mapped_column(
        ForeignKey("job_posting.id", ondelete="CASCADE"), index=True
    )
    skill_id: Mapped[str] = mapped_column(ForeignKey("skill.id", ondelete="CASCADE"), index=True)
    requirement_type: Mapped[str] = mapped_column(
        String(20), default=RequirementType.REQUIRED.value
    )
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    evidence: Mapped[str] = mapped_column(Text, default="")


class JobScore(Base):
    __tablename__ = "job_score"
    __table_args__ = (Index("ix_score_candidate_total", "candidate_id", "total"),)

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=new_id)
    job_id: Mapped[str] = mapped_column(
        ForeignKey("job_posting.id", ondelete="CASCADE"), index=True
    )
    candidate_id: Mapped[str] = mapped_column(
        ForeignKey("candidate.id", ondelete="CASCADE"), index=True
    )
    search_profile_id: Mapped[str | None] = mapped_column(
        ForeignKey("search_profile.id", ondelete="SET NULL"), nullable=True
    )
    rubric_version: Mapped[str] = mapped_column(String(20), default="1.0")
    total: Mapped[int] = mapped_column(Integer, default=0)
    band: Mapped[str] = mapped_column(String(40), default="baja")
    components: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    matched_skills: Mapped[list[str]] = mapped_column(JSON, default=list)
    missing_skills: Mapped[list[str]] = mapped_column(JSON, default=list)
    risks: Mapped[list[str]] = mapped_column(JSON, default=list)
    summary: Mapped[str] = mapped_column(Text, default="")
    model: Mapped[str] = mapped_column(String(80), default="rubrica-local")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Application(Base):
    __tablename__ = "application"
    __table_args__ = (
        UniqueConstraint("candidate_id", "job_id", name="uq_application_candidate_job"),
    )

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=new_id)
    job_id: Mapped[str] = mapped_column(
        ForeignKey("job_posting.id", ondelete="CASCADE"), index=True
    )
    candidate_id: Mapped[str] = mapped_column(
        ForeignKey("candidate.id", ondelete="CASCADE"), index=True
    )
    score_id: Mapped[str | None] = mapped_column(
        ForeignKey("job_score.id", ondelete="SET NULL"), nullable=True
    )
    resume_document_id: Mapped[str | None] = mapped_column(
        ForeignKey("candidate_document.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(30), default=ApplicationStatus.DETECTED.value, index=True
    )
    mode: Mapped[str] = mapped_column(String(30), default="assisted")
    prepared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmation_text: Mapped[str] = mapped_column(String(80), default="")
    error: Mapped[str] = mapped_column(Text, default="")
    browser_state: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class ApplicationField(Base):
    __tablename__ = "application_field"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=new_id)
    application_id: Mapped[str] = mapped_column(
        ForeignKey("application.id", ondelete="CASCADE"), index=True
    )
    field_key: Mapped[str] = mapped_column(String(240), default="")
    label: Mapped[str] = mapped_column(String(500), default="")
    field_type: Mapped[str] = mapped_column(String(40), default="text")
    value: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(80), default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    required: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(30), default="resolved")
    options: Mapped[list[str]] = mapped_column(JSON, default=list)
    step: Mapped[int] = mapped_column(Integer, default=1)


class ApplicationEvent(Base):
    __tablename__ = "application_event"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=new_id)
    application_id: Mapped[str] = mapped_column(
        ForeignKey("application.id", ondelete="CASCADE"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(40), default="note")
    message: Mapped[str] = mapped_column(Text, default="")
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AnswerBank(Base):
    __tablename__ = "answer_bank"
    __table_args__ = (UniqueConstraint("candidate_id", "key", name="uq_answer_bank_key"),)

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=new_id)
    candidate_id: Mapped[str] = mapped_column(
        ForeignKey("candidate.id", ondelete="CASCADE"), index=True
    )
    key: Mapped[str] = mapped_column(String(120), default="")
    question_pattern: Mapped[str] = mapped_column(String(500), default="")
    answer: Mapped[str] = mapped_column(Text, default="")
    answer_type: Mapped[str] = mapped_column(String(40), default="text")
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class AutomationRun(Base):
    __tablename__ = "automation_run"
    __table_args__ = (Index("ix_run_status_created", "status", "created_at"),)

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(20), default=TaskKind.SCAN.value)
    status: Mapped[str] = mapped_column(String(20), default=TaskStatus.QUEUED.value)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Artifact(Base):
    __tablename__ = "artifact"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=new_id)
    application_id: Mapped[str | None] = mapped_column(
        ForeignKey("application.id", ondelete="CASCADE"), nullable=True, index=True
    )
    run_id: Mapped[str | None] = mapped_column(
        ForeignKey("automation_run.id", ondelete="SET NULL"), nullable=True, index=True
    )
    kind: Mapped[str] = mapped_column(String(40), default="screenshot")
    path: Mapped[str] = mapped_column(String(1000), default="")
    sha256: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = (Index("ix_audit_created", "created_at"),)

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=new_id)
    actor: Mapped[str] = mapped_column(String(80), default="system")
    action: Mapped[str] = mapped_column(String(120), default="")
    entity: Mapped[str] = mapped_column(String(80), default="")
    entity_id: Mapped[str] = mapped_column(String(80), default="")
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Setting(Base):
    __tablename__ = "setting"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
