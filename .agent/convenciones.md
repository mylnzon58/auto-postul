# Convenciones

## Código

- Python 3.12+ con tipos.
- Identificadores en inglés; comentarios, docstrings y UI en español.
- Funciones pequeñas y nombres explícitos.
- Sin imports no usados, sin código muerto, sin capas innecesarias.
- Errores de negocio con excepciones propias y mensajes en español.
- Logs estructurados sin secretos ni PII.

## Base de datos

- Tablas plurales `snake_case`.
- Columnas `snake_case`; FK `<entidad>_id`.
- PK `TEXT` ULID.
- Fechas UTC con `timezone=True`.
- Enums estables con `StrEnum` y `CHECK`/validación.
- Catálogos normalizados (skills, alias).
- Migraciones Alembic; seed idempotente.
- No guardar cookies, tokens ni contraseñas.

## Web

- Server-rendered con Jinja2.
- CSS puro con tokens; sin Tailwind.
- HTMX vendorizado; JavaScript mínimo.
- Formularios con CSRF.
- HTML semántico, foco visible, contraste AA.
- Máximo 3 acciones primarias por pantalla.
- Termómetro con número, etiqueta y razones, no solo color.

## Automatización

- Un solo navegador a la vez.
- Lock de perfil entre MCP y Patchright.
- Modo dry-run por defecto.
- Pausa ante campos desconocidos.
- No reintentar un envío ambiguo.
- Capturas y eventos como evidencia.
