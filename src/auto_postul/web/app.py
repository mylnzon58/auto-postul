"""Aplicación FastAPI: panel local y API mínima de salud."""

from __future__ import annotations

import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from auto_postul.config import get_settings
from auto_postul.db.seed import seed_defaults
from auto_postul.db.session import init_db, session_scope
from auto_postul.logging import configure_logging, ensure_directories
from auto_postul.web.routes import router

PUBLIC_PATHS = {"/login", "/api/health", "/favicon.ico"}
PUBLIC_PREFIXES = ("/static/",)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings)
    ensure_directories(settings)
    init_db(settings)
    with session_scope(settings) as session:
        seed_defaults(session)
    app.state.settings = settings
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="AutoPostul", version="0.1.0", lifespan=lifespan)
    static_dir = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.middleware("http")
    async def security_and_auth(request: Request, call_next):  # type: ignore[no-untyped-def]
        session = request.session
        if "csrf" not in session:
            session["csrf"] = secrets.token_urlsafe(32)

        path = request.url.path
        if (
            settings.app_password
            and not session.get("auth")
            and path not in PUBLIC_PATHS
            and not any(path.startswith(prefix) for prefix in PUBLIC_PREFIXES)
        ):
            return RedirectResponse(url="/login", status_code=303)

        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
            "script-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        )
        return response

    # Se agrega al final para que sea el middleware más externo y request.session exista.
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret,
        same_site="strict",
        https_only=False,
        max_age=60 * 60 * 24 * 14,
    )
    app.include_router(router)
    return app


app = create_app()
