"""Base declarativa y utilidades comunes para SQLAlchemy."""

from __future__ import annotations

import os
import time
from datetime import UTC, datetime

from sqlalchemy.orm import DeclarativeBase

_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def new_id() -> str:
    """Genera un ULID de 26 caracteres sin dependencias externas."""
    timestamp = int(time.time() * 1000)
    random_part = int.from_bytes(os.urandom(10), "big")
    value = (timestamp << 80) | random_part
    return "".join(_ALPHABET[(value >> (5 * (25 - index))) & 31] for index in range(26))


def utcnow() -> datetime:
    """Fecha UTC con zona horaria explícita."""
    return datetime.now(UTC)


class Base(DeclarativeBase):
    """Base común de todos los modelos."""
