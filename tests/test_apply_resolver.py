from __future__ import annotations

from pathlib import Path

from auto_postul.config import get_settings
from auto_postul.domain.schemas import FormField
from auto_postul.infrastructure.linkedin_apply import ApplyContext, _resolve_fields


def test_resolve_known_fields_and_pause_unknown() -> None:
    context = ApplyContext(
        application_id="app-test",
        job_url="https://www.linkedin.com/jobs/view/1/",
        candidate={
            "email": "ana@example.com",
            "phone": "+54 11 5555 0000",
            "location": "Argentina",
            "years_experience": "6",
        },
        answers={
            "first_name": "Ana",
            "last_name": "Perez",
            "work_authorization": "Sí",
        },
        resume_path=Path("/tmp/cv.pdf"),
        settings=get_settings(),
    )
    fields = [
        FormField(key="email", label="Email", field_type="email", required=True),
        FormField(key="firstName", label="First name", field_type="text", required=True),
        FormField(
            key="auth", label="Are you authorized to work?", field_type="select", required=True
        ),
        FormField(
            key="why", label="Why do you want this job?", field_type="textarea", required=True
        ),
    ]

    resolved = _resolve_fields(fields, context)

    assert resolved[0].value == "ana@example.com"
    assert resolved[0].status == "resolved"
    assert resolved[1].value == "Ana"
    assert resolved[2].value == "Sí"
    assert resolved[3].status == "pending"
