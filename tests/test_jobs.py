from __future__ import annotations

from auto_postul.domain.jobs import parse_job_payload


def test_parse_job_payload_from_mcp_text() -> None:
    payload = {
        "url": "https://www.linkedin.com/jobs/view/123/",
        "sections": {
            "job_posting": (
                "Backend Engineer\n"
                "Acme\n"
                "Remote\n"
                "About the job\n"
                "Buscamos Backend Engineer con Python, PostgreSQL y Docker.\n"
                "Requirements\n"
                "Python\nPostgreSQL\nDocker\n"
                "Benefits\nSeguro médico\n"
            )
        },
        "apply": {"type": "easy_apply"},
    }

    job = parse_job_payload(payload, "123", payload["url"])

    assert job.title == "Backend Engineer"
    assert job.company == "Acme"
    assert job.work_mode == "remote"
    assert job.apply_type == "easy_apply"
    assert job.job_family == "full_stack"
    assert "python" in job.required_skills
    assert "docker" in job.required_skills


def test_external_apply_is_detected() -> None:
    payload = {
        "sections": {"job_posting": "Data Engineer\nBeta\nRemote\nAbout the job\nPython"},
        "apply": {"type": "external"},
    }

    job = parse_job_payload(payload, "456", "https://example.com/job")

    assert job.apply_type == "external"


def test_external_header_wins_over_similar_jobs_text() -> None:
    payload = {
        "sections": {
            "job_posting": (
                "Acme\nQuality Analyst\nArgentina\n"
                "Respuestas gestionadas fuera de LinkedIn\nEn remoto\nSolicitar\n"
                "Acerca del empleo\nDescripción real.\n"
                "Empleos similares\nOtra oferta\nSolicitud sencilla\n"
            )
        },
        "apply": {"type": "unknown"},
    }

    job = parse_job_payload(payload, "789", "https://www.linkedin.com/jobs/view/789/")

    assert job.apply_type == "external"


def test_easy_apply_header_is_detected() -> None:
    payload = {
        "sections": {
            "job_posting": (
                "Acme\nBackend Engineer\nArgentina\n"
                "Solicitud sencilla\nGuardar\n"
                "Acerca del empleo\nPython y Docker.\n"
            )
        },
        "apply": {"type": "unknown"},
    }

    job = parse_job_payload(payload, "790", "https://www.linkedin.com/jobs/view/790/")

    assert job.apply_type == "easy_apply"
