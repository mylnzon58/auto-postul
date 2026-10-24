from __future__ import annotations

from auto_postul.domain.scoring import CandidateSnapshot, JobSnapshot, band_for, score_job


def candidate() -> CandidateSnapshot:
    return CandidateSnapshot(
        skills={"python": "Python", "postgresql": "PostgreSQL", "docker": "Docker"},
        target_titles=["Backend Engineer"],
        tracks=["full_stack"],
        location="Argentina",
        work_modes=["remote"],
        years_experience=6,
        english_level="B2",
        has_degree=True,
        headline="Backend Engineer",
    )


def job() -> JobSnapshot:
    return JobSnapshot(
        title="Backend Engineer",
        company="Acme",
        location="Remote",
        work_mode="remote",
        description="We need Python, PostgreSQL and Docker. 3 years of experience.",
        requirements="Python, PostgreSQL, Docker",
        job_family="full_stack",
        apply_type="easy_apply",
    )


def test_high_match_scores_high() -> None:
    result = score_job(
        candidate(),
        job(),
        [
            ("python", "Python", "required"),
            ("postgresql", "PostgreSQL", "required"),
            ("docker", "Docker", "required"),
        ],
    )

    assert result.total >= 75
    assert result.band in ("alta", "muy_alta")
    assert "Python" in result.matched_skills
    assert not result.missing_skills


def test_missing_required_skills_caps_score() -> None:
    result = score_job(
        candidate(),
        job(),
        [
            ("python", "Python", "required"),
            ("kubernetes", "Kubernetes", "required"),
            ("go", "Go", "required"),
        ],
    )

    assert result.total <= 50
    assert "Kubernetes" in result.missing_skills
    assert result.risks


def test_fluent_english_caps_spanish_basic_candidate() -> None:
    basic = candidate()
    basic.english_level = "A1 / básico"
    fluent_job = job()
    fluent_job.description = "Fluent English required. " + fluent_job.description

    result = score_job(basic, fluent_job, [("python", "Python", "required")])

    assert result.total <= 55
    assert any("inglés" in risk.casefold() for risk in result.risks)


def test_bands() -> None:
    assert band_for(95) == "muy_alta"
    assert band_for(80) == "alta"
    assert band_for(65) == "media"
    assert band_for(45) == "media_baja"
    assert band_for(10) == "baja"


def test_off_target_role_caps_score() -> None:
    off_target = job()
    off_target.title = "Embedded Engineer"
    off_target.job_family = "full_stack"

    result = score_job(
        candidate(),
        off_target,
        [("python", "Python", "required")],
    )

    assert result.total <= 55
    assert any("fuera de los roles objetivo" in risk for risk in result.risks)
