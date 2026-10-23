---
name: datos-y-migraciones
description: Usar cuando se agreguen o cambien tablas, columnas, índices, enums, seeds o relaciones en AutoPostul.
---

# Datos y migraciones

- Tablas plurales en `snake_case`.
- Columnas `snake_case`; FK `<entidad>_id`.
- PK `TEXT` ULID; sin autoincrementos expuestos.
- Fechas UTC con `timezone=True`.
- Enums pequeños con `StrEnum` y validación/`CHECK`.
- Catálogos normalizados; no repetir strings de skills.
- `ON DELETE` explícito.
- Índices para búsquedas reales, no por reflejo.
- Migración Alembic por cambio de esquema.
- Seed idempotente.
- Tests con base limpia y `foreign_keys=ON`.
- No guardar secretos, cookies ni PII innecesaria.
- Ejecutar `alembic check` o verificar que no haya deriva entre modelos y migraciones.
