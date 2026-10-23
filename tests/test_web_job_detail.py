from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from auto_postul.db.base import new_id, utcnow
from auto_postul.db.models import (
    Application,
    ApplicationField,
    JobPosting,
    JobScore,
    JobSkill,
    Skill,
)
from auto_postul.db.seed import get_or_create_candidate
from auto_postul.db.session import session_scope


def test_job_detail_and_review_render(client: TestClient) -> None:
    with session_scope() as session:
        candidate = get_or_create_candidate(session)
        assert candidate is not None
        job = JobPosting(
            source="test",
            external_id=new_id(),
            url="https://www.linkedin.com/jobs/view/1/",
            title="Backend Engineer",
            company_name="Acme",
            location="Remote",
            work_mode="remote",
            apply_type="easy_apply",
            job_family="full_stack",
            description="Python, PostgreSQL y Docker.",
            requirements="Python y Docker.",
        )
        session.add(job)
        session.flush()
        skill = session.scalars(select(Skill).where(Skill.slug == "python")).first()
        if skill is not None:
            session.add(
                JobSkill(
                    job_id=job.id,
                    skill_id=skill.id,
                    requirement_type="required",
                    evidence="Python",
                )
            )
        score = JobScore(
            job_id=job.id,
            candidate_id=candidate.id,
            total=82,
            band="alta",
            components=[
                {
                    "key": "required_skills",
                    "label": "Skills obligatorias",
                    "weight": 30,
                    "raw": 0.8,
                    "points": 24,
                    "evidence": "4/5",
                }
            ],
            matched_skills=["Python"],
            missing_skills=["Docker"],
            risks=["Falta Docker"],
            summary="Afinidad 82/100.",
        )
        session.add(score)
        session.flush()
        application = Application(
            job_id=job.id,
            candidate_id=candidate.id,
            score_id=score.id,
            status="ready_for_review",
            prepared_at=utcnow(),
        )
        session.add(application)
        session.flush()
        session.add(
            ApplicationField(
                application_id=application.id,
                field_key="email",
                label="Email",
                field_type="email",
                value="ana@example.com",
                source="perfil",
                required=True,
                status="resolved",
                step=1,
            )
        )
        job_id = job.id
        application_id = application.id

    job_response = client.get(f"/jobs/{job_id}")
    assert job_response.status_code == 200
    assert "Backend Engineer" in job_response.text
    assert "Por qué puntúa así" in job_response.text

    app_response = client.get(f"/applications/{application_id}")
    assert app_response.status_code == 200
    assert "Confirmar envío" in app_response.text
    assert "ana@example.com" in app_response.text
