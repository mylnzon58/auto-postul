from __future__ import annotations

from pathlib import Path

import pytest

from auto_postul.config import Settings
from auto_postul.infrastructure.linkedin_apply import (
    ApplyContext,
    close_application,
    prepare_application,
    submit_application,
)

HTML = """<!doctype html><html><body>
<main>
<h1>Backend Engineer</h1>
<a href="#/apply/" onclick="document.getElementById('dialog').style.display='block'; return false;">Easy Apply</a>
<div id="dialog" role="dialog" style="display:none">
  <form>
    <label for="email">Email *</label><input id="email" name="email" type="email" required>
    <label for="first">First name *</label><input id="first" name="first" type="text" required>
    <label for="last">Last name *</label><input id="last" name="last" type="text" required>
    <label for="auth">Are you authorized to work? *</label>
    <select id="auth" name="auth" required><option>Sí</option><option>No</option></select>
    <input type="file" id="resume" name="resume">
    <button type="button" onclick="document.getElementById('review').style.display='block'">Next</button>
    <p id="review" style="display:none">Review your application</p>
  </form>
</div>
</main></body></html>"""


@pytest.mark.integration
async def test_prepare_and_dry_run_submit(tmp_path: Path) -> None:
    from patchright.async_api import async_playwright

    try:
        async with async_playwright() as playwright:
            executable = Path(playwright.chromium.executable_path)
            if not executable.exists():
                pytest.skip("Chromium de Patchright no instalado.")
    except Exception:
        pytest.skip("Patchright no disponible.")

    html = tmp_path / "job.html"
    html.write_text(HTML, encoding="utf-8")
    resume = tmp_path / "cv.pdf"
    resume.write_bytes(b"%PDF-1.4\nprueba")
    settings = Settings(
        app_data_dir=tmp_path,
        apply_headless=True,
        apply_dry_run=True,
        apply_live_submit=False,
        apply_action_delay_ms=10,
        apply_max_steps=5,
    )
    context = ApplyContext(
        application_id="app-integration",
        job_url=html.as_uri(),
        candidate={
            "email": "ana@example.com",
            "phone": "123",
            "full_name": "Ana Perez",
            "location": "Argentina",
            "years_experience": "6",
        },
        answers={"first_name": "Ana", "last_name": "Perez", "work_authorization": "Sí"},
        resume_path=resume,
        settings=settings,
    )

    try:
        result = await prepare_application(context)
        assert result.status == "ready_for_review"
        assert any(field.value == "ana@example.com" for field in result.fields)
        assert not [
            field for field in result.fields if field.required and field.status == "pending"
        ]

        submit = await submit_application("app-integration", settings)
        assert submit.status == "dry_run"
        assert submit.confirmed is False
    finally:
        await close_application("app-integration")
