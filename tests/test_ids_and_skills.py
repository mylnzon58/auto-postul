from __future__ import annotations

from auto_postul.db.base import new_id
from auto_postul.domain.skills import detect_skills


def test_ulid_shape() -> None:
    value = new_id()
    assert len(value) == 26
    assert value.isalnum()
    assert value == value.upper()


def test_skill_detection_avoids_substring_false_positives() -> None:
    skills = {skill.slug for skill in detect_skills("Java y JavaScript, C++ y CSS. Python.")}

    assert "javascript" in skills
    assert "java" in skills
    assert "cpp" in skills
    assert "css" in skills
    assert "python" in skills


def test_google_ads_search_ranks_as_its_own_skill() -> None:
    skills = {skill.slug for skill in detect_skills("Especialista en Google Ads Search y SEM.")}

    assert "google-ads-search" in skills
