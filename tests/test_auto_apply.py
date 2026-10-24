from __future__ import annotations

import pytest

from auto_postul.application.auto_apply import (
    eligible_jobs,
    get_auto_settings,
    save_auto_settings,
)
from auto_postul.application.prepare import ApplicationError, submit
from auto_postul.config import get_settings
from auto_postul.db.base import new_id
from auto_postul.db.models import Application, JobPosting, JobScore
from auto_postul.db.seed import get_or_create_candidate
from auto_postul.db.session import session_scope


def test_auto_settings_roundtrip() -> None:
    with session_scope() as session:
        saved = save_auto_settings(
            session,
            {
                "enabled": True,
                "min_score": 85,
                "daily_limit": 3,
                "delay_min_seconds": 30,
                "delay_max_seconds": 90,
                "remote_only": True,
            },
        )
        loaded = get_auto_settings(session)
    assert saved.enabled is True
    assert loaded.min_score == 85
    assert loaded.daily_limit == 3
    assert loaded.delay_max_seconds == 90


def test_eligible_jobs_only_remote_high_score_without_submission() -> None:
    with session_scope() as session:
        candidate = get_or_create_candidate(session)
        config = get_auto_settings(session)
        config.min_score = 80
        config.remote_only = True
        eligible = JobPosting(
            source="test",
            external_id=new_id(),
            title="AI Engineer",
            company_name="Acme",
            work_mode="remote",
            apply_type="easy_apply",
        )
        remote_low = JobPosting(
            source="test",
            external_id=new_id(),
            title="Low Score",
            company_name="Acme",
            work_mode="remote",
            apply_type="easy_apply",
        )
        on_site = JobPosting(
            source="test",
            external_id=new_id(),
            title="On Site",
            company_name="Acme",
            work_mode="on_site",
            apply_type="easy_apply",
        )
        session.add_all([eligible, remote_low, on_site])
        session.flush()
        session.add_all(
            [
                JobScore(job_id=eligible.id, candidate_id=candidate.id, total=92, band="muy_alta"),
                JobScore(
                    job_id=remote_low.id, candidate_id=candidate.id, total=50, band="media_baja"
                ),
                JobScore(job_id=on_site.id, candidate_id=candidate.id, total=95, band="muy_alta"),
            ]
        )
        session.flush()
        chosen = eligible_jobs(session, candidate, config)
        assert [job.id for job, _score in chosen] == [eligible.id]


def test_auto_apply_disabled_is_rejected() -> None:
    with session_scope() as session:
        save_auto_settings(session, {"enabled": False})
        with pytest.raises(ApplicationError):
            import asyncio

            from auto_postul.application.auto_apply import run_auto_apply

            asyncio.run(run_auto_apply(session, get_settings()))


def test_daily_apply_limit_blocks_manual_submit() -> None:
    with session_scope() as session:
        candidate = get_or_create_candidate(session)
        job = JobPosting(
            source="test",
            external_id=new_id(),
            title="Limit",
            company_name="Acme",
            apply_type="easy_apply",
        )
        session.add(job)
        session.flush()
        application = Application(
            candidate_id=candidate.id,
            job_id=job.id,
            status="ready_for_review",
        )
        session.add(application)
        session.flush()
        settings = get_settings()
        old_limit = settings.daily_apply_limit
        settings.daily_apply_limit = 0
        try:
            with pytest.raises(ApplicationError):
                import asyncio

                asyncio.run(submit(session, settings, application.id, confirmation="ENVIAR"))
        finally:
            settings.daily_apply_limit = old_limit
