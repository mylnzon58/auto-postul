"""Punto de entrada del worker: `python -m auto_postul.worker`."""

from __future__ import annotations

import asyncio
import logging

from auto_postul.application.prepare import ApplicationError, prepare, submit
from auto_postul.application.queue import claim_next, fail, finish, touch_worker
from auto_postul.application.scan import run_scan
from auto_postul.config import get_settings
from auto_postul.db.seed import seed_defaults
from auto_postul.db.session import init_db, session_scope
from auto_postul.domain.enums import TaskKind
from auto_postul.infrastructure.linkedin_mcp import LinkedInMcpClient
from auto_postul.logging import configure_logging

logger = logging.getLogger(__name__)


async def execute(kind: str, payload: dict[str, object]) -> dict[str, object]:
    settings = get_settings()
    if kind == TaskKind.SCAN.value:
        with session_scope(settings) as session:
            return await run_scan(
                session,
                settings,
                search_profile_id=str(payload.get("search_profile_id") or "") or None,
            )
    if kind == TaskKind.PREPARE.value:
        with session_scope(settings) as session:
            application, prepare_result = await prepare(
                session, settings, str(payload.get("job_id") or "")
            )
            return {
                "application_id": application.id,
                "status": prepare_result.status,
                "message": prepare_result.message,
            }
    if kind == TaskKind.SUBMIT.value:
        with session_scope(settings) as session:
            application, submit_result = await submit(
                session,
                settings,
                str(payload.get("application_id") or ""),
                confirmation=str(payload.get("confirmation") or ""),
            )
            return {
                "application_id": application.id,
                "status": submit_result.status,
                "message": submit_result.message,
            }
    if kind == TaskKind.LOGIN.value:
        code = await LinkedInMcpClient(settings).login()
        return {"exit_code": code, "message": "Login de LinkedIn finalizado."}
    raise ApplicationError(f"Tipo de tarea desconocido: {kind}")


async def heartbeat(settings) -> None:  # type: ignore[no-untyped-def]
    """Mantiene vivo el estado del worker mientras procesa tareas largas."""
    while True:
        with session_scope(settings) as session:
            touch_worker(session)
        await asyncio.sleep(5)


async def loop() -> None:
    settings = get_settings()
    configure_logging(settings)
    init_db(settings)
    with session_scope(settings) as session:
        seed_defaults(session)
        touch_worker(session)
    logger.info("Worker iniciado")
    background: set[asyncio.Task[None]] = set()
    heartbeat_task = asyncio.create_task(heartbeat(settings))
    background.add(heartbeat_task)
    heartbeat_task.add_done_callback(background.discard)
    while True:
        with session_scope(settings) as session:
            run = claim_next(session)
        if run is None:
            await asyncio.sleep(2)
            continue
        logger.info("Ejecutando %s %s", run.kind, run.id)
        try:
            result = await execute(run.kind, dict(run.payload or {}))
            with session_scope(settings) as session:
                current = session.get(type(run), run.id)
                if current is not None:
                    finish(session, current, result=result)
        except Exception as exc:
            logger.exception("Falló la tarea %s", run.id)
            with session_scope(settings) as session:
                current = session.get(type(run), run.id)
                if current is not None:
                    fail(session, current, str(exc))


def main() -> None:
    try:
        asyncio.run(loop())
    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    main()
