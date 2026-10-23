"""Dependencias de la capa web."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy.orm import Session

from auto_postul.db.session import session_scope


def get_db() -> Iterator[Session]:
    """Sesión por request, con commit al terminar."""
    with session_scope() as session:
        yield session
