"""Cliente MCP de LinkedIn, aislado detrás de un puerto fácil de sustituir."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import time
from collections import deque
from contextlib import AsyncExitStack
from typing import Any

from auto_postul.config import Settings

logger = logging.getLogger(__name__)


class LinkedInMcpError(RuntimeError):
    """Error legible del servidor MCP o de su proceso."""


class McpRateLimiter:
    """Límite conservador en memoria para no saturar la cuenta."""

    def __init__(self, calls_per_minute: int):
        self.calls_per_minute = max(1, calls_per_minute)
        self._calls: deque[float] = deque()

    async def wait(self) -> None:
        now = time.monotonic()
        while self._calls and now - self._calls[0] > 60:
            self._calls.popleft()
        if len(self._calls) >= self.calls_per_minute:
            sleep_for = 60 - (now - self._calls[0]) + 0.5
            await asyncio.sleep(max(0.5, sleep_for))
        self._calls.append(time.monotonic())


def _server_command(settings: Settings) -> list[str]:
    uvx = shutil.which("uvx")
    if not uvx:
        raise LinkedInMcpError(
            "No se encontró uvx. Instalá uv con `curl -LsSf https://astral.sh/uv/install.sh | sh`."
        )
    return [uvx, f"mcp-server-linkedin@{settings.linkedin_mcp_version}"]


def _mcp_environment(settings: Settings) -> dict[str, str]:
    env = dict(os.environ)
    env.update(
        {
            "USER_DATA_DIR": str(settings.linkedin_profile_dir),
            "HEADLESS": "true" if settings.linkedin_headless else "false",
            "TRANSPORT": "stdio",
            "LOG_LEVEL": "WARNING",
            "TOOL_TIMEOUT": str(settings.linkedin_tool_timeout),
            "AUTO_IMPORT_FROM_BROWSER": "false",
            "LINKEDIN_MCP_CHECK_FOR_UPDATES": "false",
        }
    )
    return env


def _parse_tool_result(result: Any) -> dict[str, Any]:
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        return structured
    content = getattr(result, "content", None) or []
    for block in content:
        text = getattr(block, "text", None)
        if not text:
            continue
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return {"text": text}
        if isinstance(parsed, dict):
            return parsed
    return {}


class LinkedInMcpClient:
    """Una sesión MCP por operación para liberar el navegador al terminar."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._stack: AsyncExitStack | None = None
        self._session: Any | None = None
        self._limiter = McpRateLimiter(settings.mcp_calls_per_minute)

    async def __aenter__(self) -> LinkedInMcpClient:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        self._stack = AsyncExitStack()
        try:
            params = StdioServerParameters(
                command=_server_command(self.settings)[0],
                args=_server_command(self.settings)[1:],
                env=_mcp_environment(self.settings),
            )
            read_stream, write_stream = await self._stack.enter_async_context(stdio_client(params))
            self._session = await self._stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )
            assert self._session is not None
            await self._session.initialize()
        except Exception as exc:
            await self._stack.aclose()
            self._stack = None
            self._session = None
            raise LinkedInMcpError(f"No se pudo iniciar el MCP de LinkedIn: {exc}") from exc
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        if self._stack is not None:
            await self._stack.aclose()
        self._stack = None
        self._session = None

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if self._session is None:
            raise LinkedInMcpError("La sesión MCP no está iniciada.")
        await self._limiter.wait()
        try:
            result = await self._session.call_tool(name, arguments)
        except Exception as exc:
            raise LinkedInMcpError(f"{name} falló: {exc}") from exc
        if getattr(result, "isError", False):
            raise LinkedInMcpError(f"{name} devolvió un error: {_parse_tool_result(result)}")
        return _parse_tool_result(result)

    async def search_jobs(
        self,
        keywords: str,
        *,
        location: str,
        max_pages: int = 1,
        date_posted: str = "past_week",
        work_type: str = "remote",
        job_type: str = "full_time",
        experience_level: str = "",
        easy_apply: bool = True,
    ) -> dict[str, Any]:
        return await self.call_tool(
            "search_jobs",
            {
                "keywords": keywords,
                "location": location,
                "max_pages": max(1, min(3, max_pages)),
                "date_posted": date_posted,
                "work_type": work_type,
                "job_type": job_type,
                "experience_level": experience_level,
                "easy_apply": easy_apply,
                "sort_by": "relevance",
            },
        )

    async def get_job_details(self, job_id: str) -> dict[str, Any]:
        return await self.call_tool("get_job_details", {"job_id": job_id})

    async def get_job_apply_url(self, job_id: str) -> dict[str, Any]:
        return await self.call_tool("get_job_apply_url", {"job_id": job_id})

    async def get_saved_jobs(self, stage: str = "applied", max_pages: int = 1) -> dict[str, Any]:
        return await self.call_tool("get_saved_jobs", {"stage": stage, "max_pages": max_pages})

    async def close_session(self) -> None:
        try:
            await self.call_tool("close_session", {})
        except Exception:
            logger.debug("El MCP ya estaba cerrado", exc_info=True)

    async def login(self) -> int:
        """Abre el navegador visible del MCP y espera a que el usuario termine."""
        command = _server_command(self.settings)
        command.extend(
            [
                "--login",
                "--user-data-dir",
                str(self.settings.linkedin_profile_dir),
            ]
        )
        if (
            self.settings.linkedin_parent_dir.exists()
            and not (self.settings.linkedin_parent_dir / "profile-claim.json").exists()
        ):
            command.append("--claim-profile-root")
        env = _mcp_environment(self.settings)
        env["HEADLESS"] = "false"
        logger.info("Abriendo login de LinkedIn")
        process = await asyncio.create_subprocess_exec(
            *command,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        output, _ = await process.communicate()
        text = (output or b"").decode(errors="replace").strip()
        if text:
            logger.info("Login MCP: %s", text[-2000:])
        return int(process.returncode or 0)
