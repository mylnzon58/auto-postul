from __future__ import annotations

from auto_postul.domain.cv import parse_cv_text

SAMPLE_CV = """ANA PEREZ
Backend Engineer | Python
Buenos Aires, Argentina · Trabajo remoto
ana@example.com · +54 11 5555 0000
linkedin.com/in/ana-perez · github.com/anaperez

PERFIL PROFESIONAL
Desarrolladora backend con más de 6 años de experiencia en Python, PostgreSQL y Docker.

EXPERIENCIA PROFESIONAL
Backend Developer
Acme SA | 01/2021 – Actualidad
APIs REST con Python y PostgreSQL.

Data Engineer
Beta LLC | 2018 – 2020
Pipelines de datos y Docker.

FORMACIÓN Y CERTIFICACIONES
Ingeniería en Sistemas — Universidad | 2015 – 2020

IDIOMAS
Español: nativo · Inglés: B2
"""


def test_parse_cv_extracts_identity_and_skills() -> None:
    result = parse_cv_text(SAMPLE_CV)

    assert result.full_name == "ANA PEREZ"
    assert result.email == "ana@example.com"
    assert result.years_experience == 6.0
    assert "python" in result.skills
    assert "postgresql" in result.skills
    assert "docker" in result.skills
    assert ("Inglés", "B2") in result.languages


def test_parse_cv_extracts_multiple_experiences() -> None:
    result = parse_cv_text(SAMPLE_CV)

    assert len(result.experiences) == 2
    assert result.experiences[0].title == "Backend Developer"
    assert result.experiences[0].company == "Acme SA"
    assert result.experiences[0].is_current is True
    assert result.experiences[1].title == "Data Engineer"
    assert result.experiences[1].company == "Beta LLC"


def test_parse_cv_does_not_confuse_java_with_javascript() -> None:
    result = parse_cv_text(SAMPLE_CV + "\nJavaScript y React.\n")

    assert "javascript" in result.skills
    assert "java" not in result.skills
