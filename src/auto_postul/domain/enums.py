"""Enumeraciones estables del dominio."""

from __future__ import annotations

from enum import StrEnum


class ApplyType(StrEnum):
    EASY_APPLY = "easy_apply"
    EXTERNAL = "external"
    APPLIED = "applied"
    CLOSED = "closed"
    UNKNOWN = "unknown"


class ApplicationStatus(StrEnum):
    DETECTED = "detected"
    SCORED = "scored"
    SHORTLISTED = "shortlisted"
    PREPARING = "preparing"
    NEEDS_INPUT = "needs_input"
    READY_FOR_REVIEW = "ready_for_review"
    SUBMITTING = "submitting"
    SUBMITTED = "submitted"
    FAILED = "failed"
    SKIPPED = "skipped"
    SUBMISSION_UNKNOWN = "submission_unknown"


class RequirementType(StrEnum):
    REQUIRED = "required"
    NICE = "nice"


class TaskKind(StrEnum):
    SCAN = "scan"
    PREPARE = "prepare"
    SUBMIT = "submit"
    AUTO_APPLY = "auto_apply"
    LOGIN = "login"


class TaskStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


class EventType(StrEnum):
    CREATED = "created"
    STATUS_CHANGED = "status_changed"
    FIELD_RESOLVED = "field_resolved"
    FIELD_UNKNOWN = "field_unknown"
    SUBMITTED = "submitted"
    SUBMISSION_UNKNOWN = "submission_unknown"
    ERROR = "error"
    NOTE = "note"


class WorkMode(StrEnum):
    REMOTE = "remote"
    HYBRID = "hybrid"
    ON_SITE = "on_site"
    UNKNOWN = "unknown"
