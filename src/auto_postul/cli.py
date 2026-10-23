"""CLI mínima para operaciones locales sin abrir el panel."""

from __future__ import annotations

import argparse
import asyncio

from auto_postul.application.cv_import import discover_root_pdfs, import_cv_from_path
from auto_postul.application.scan import run_scan
from auto_postul.config import get_settings
from auto_postul.db.seed import seed_defaults
from auto_postul.db.session import init_db, session_scope
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


def main() -> None:
    parser = argparse.ArgumentParser(description="AutoPostul CLI")
    parser.add_argument("command", choices=["login", "import-cv", "scan", "serve"])
    args = parser.parse_args()
    if args.command == "login":
        raise SystemExit(asyncio.run(_login()))
    if args.command == "import-cv":
        asyncio.run(_import_cv())
        return
    if args.command == "scan":
        asyncio.run(_scan())
        return
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
