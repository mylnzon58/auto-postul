"""CLI mínima para operaciones locales sin abrir el panel."""

from __future__ import annotations

import argparse
import asyncio
import os
import shutil
from pathlib import Path

from sqlalchemy import select, text

from auto_postul.application.cv_import import discover_root_pdfs, import_cv_from_path
from auto_postul.application.scan import run_scan
from auto_postul.config import get_settings
from auto_postul.db.models import AutomationRun, Candidate, CandidateDocument
from auto_postul.db.seed import seed_defaults
from auto_postul.db.session import init_db, session_scope
from auto_postul.domain.enums import TaskStatus
from auto_postul.infrastructure.linkedin_mcp import LinkedInMcpClient
from auto_postul.logging import configure_logging


async def _login() -> int:
    settings = get_settings()
    configure_logging(settings)
    return await LinkedInMcpClient(settings).login()


async def _import_cv() -> None:
    settings = get_settings()
    configure_logging(settings)
    init_db(settings)
    pdfs = discover_root_pdfs(settings)
    if not pdfs:
        raise SystemExit("No encontré PDFs en la raíz del proyecto.")
    with session_scope(settings) as session:
        seed_defaults(session)
        for path in pdfs:
            await import_cv_from_path(session, path, settings)
            print(f"Importado: {path.name}")


async def _scan() -> None:
    settings = get_settings()
    configure_logging(settings)
    init_db(settings)
    with session_scope(settings) as session:
        seed_defaults(session)
    with session_scope(settings) as session:
        result = await run_scan(session, settings)
    print(result)


def _line(status: str, label: str, detail: str = "") -> None:
    print(f"[{status}] {label}" + (f" — {detail}" if detail else ""))


async def _ping_gemini() -> bool:
    settings = get_settings()
    if not settings.gemini_enabled:
        _line("WARN", "Gemini", "sin GEMINI_API_KEY; se usará la heurística local")
        return True
    from google import genai

    client = genai.Client(api_key=settings.gemini_api_key)
    try:
        response = await client.aio.models.generate_content(
            model=settings.gemini_model,
            contents='Devuelve exactamente este JSON: {"status":"ok"}',
        )
        _line("OK", "Gemini", f"responde con {settings.gemini_model}")
        return bool((response.text or "").strip())
    except Exception as exc:
        _line("ERROR", "Gemini", f"{type(exc).__name__}: {str(exc)[:180]}")
        return False


def _doctor(ping_gemini: bool) -> int:
    settings = get_settings()
    errors = 0
    configure_logging(settings)

    if Path(".env").exists():
        mode = oct(os.stat(".env").st_mode & 0o777)
        _line("OK" if mode == "0o600" else "WARN", ".env", f"permisos {mode}")
    else:
        _line("WARN", ".env", "no existe; se usan valores por defecto")

    _line("OK", "Datos", str(settings.data_dir))
    _line("OK", "Base", str(settings.database_path))
    _line("OK", "Modo seguro", "activo" if settings.apply_dry_run else "desactivado")
    _line(
        "OK" if not settings.live_submit_enabled else "WARN",
        "Envío live",
        "habilitado" if settings.live_submit_enabled else "bloqueado",
    )

    try:
        init_db(settings)
        with session_scope(settings) as session:
            version = session.execute(text("SELECT version_num FROM alembic_version")).scalar()
            candidates = session.scalars(select(Candidate)).all()
            docs = session.scalars(select(CandidateDocument)).all()
            running = session.scalars(
                select(AutomationRun).where(AutomationRun.status == TaskStatus.RUNNING.value)
            ).all()
            _line("OK", "SQLite", f"migración {version or 'sin versión'}")
            _line("OK", "Perfiles", str(len(candidates)))
            _line("OK", "CVs", str(len(docs)))
            if running:
                _line("WARN", "Cola", f"{len(running)} tarea(s) en ejecución")
    except Exception as exc:
        _line("ERROR", "SQLite", f"{type(exc).__name__}: {exc}")
        errors += 1

    uvx = shutil.which("uvx")
    _line("OK" if uvx else "ERROR", "uvx", uvx or "no encontrado")
    if not uvx:
        errors += 1

    try:
        from patchright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            executable = Path(playwright.chromium.executable_path)
            _line("OK" if executable.exists() else "ERROR", "Chromium", str(executable))
            if not executable.exists():
                errors += 1
    except Exception as exc:
        _line("ERROR", "Chromium", f"{type(exc).__name__}: {exc}")
        errors += 1

    profile = settings.linkedin_profile_dir
    has_session = any(profile.iterdir()) if profile.exists() else False
    _line(
        "OK" if has_session else "WARN",
        "LinkedIn",
        "perfil con datos" if has_session else "requiere login",
    )

    if ping_gemini:
        if not asyncio.run(_ping_gemini()):
            errors += 1
    else:
        _line(
            "OK" if settings.gemini_enabled else "WARN",
            "Gemini",
            "clave presente" if settings.gemini_enabled else "sin clave",
        )

    return 1 if errors else 0


def main() -> None:
    parser = argparse.ArgumentParser(description="AutoPostul CLI")
    parser.add_argument("command", choices=["login", "import-cv", "scan", "serve", "doctor"])
    parser.add_argument("--ping-gemini", action="store_true")
    args = parser.parse_args()
    if args.command == "login":
        raise SystemExit(asyncio.run(_login()))
    if args.command == "import-cv":
        asyncio.run(_import_cv())
        return
    if args.command == "scan":
        asyncio.run(_scan())
        return
    if args.command == "doctor":
        raise SystemExit(_doctor(args.ping_gemini))
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "auto_postul.web.app:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=False,
    )


if __name__ == "__main__":
    main()
