# AutoPostul — contexto para agentes

## Qué es

AutoPostul es una aplicación local que importa un CV, entiende el perfil, busca ofertas Easy Apply en LinkedIn, calcula afinidad CV–oferta y prepara el formulario de postulación. El envío siempre requiere confirmación humana.

El repo público es `mylnzon58/auto-postul`. El CV real, `.env`, la base SQLite, capturas y credenciales nunca se commitean.

## Reglas no negociables

1. El CV original no se modifica. Solo se extraen datos y se muestran sugerencias.
2. No inventar experiencia, skills, fechas, salarios ni respuestas.
3. Si falta un dato obligatorio, la preparación se detiene.
4. Nunca enviar una postulación sin confirmación explícita del usuario.
5. Ante CAPTCHA, 2FA, checkpoint o rate limit, detenerse. No evadir controles.
6. No hacer scraping masivo, no enviar mensajes, no conectar contactos.
7. No commitear PII, secretos, bases de datos ni artefactos.
8. El modo seguro (`APPLY_DRY_RUN=true`) es el default.

## Stack

- Python 3.12+ (proyecto fijado a 3.13 con uv).
- FastAPI, Jinja2, HTMX vendorizado, CSS puro.
- SQLAlchemy 2 + Alembic + SQLite WAL.
- Patchright para Easy Apply.
- `mcp-server-linkedin` pinneado para lectura de LinkedIn.
- Google AI Studio / Gemini mediante `google-genai`.

## Arquitectura

- `src/auto_postul/domain/`: reglas puras. No importa FastAPI, SQLAlchemy, Patchright ni Gemini.
- `src/auto_postul/application/`: casos de uso y cola.
- `src/auto_postul/infrastructure/`: adaptadores MCP, navegador, Gemini, archivos.
- `src/auto_postul/web/`: rutas, templates y estáticos.
- `src/auto_postul/worker/`: procesa la cola SQLite.
- `src/auto_postul/db/`: modelos, sesión y seed.

La UI no ejecuta el navegador: encola tareas. El worker es el único dueño del navegador.

## Convenciones

- Documentación, UI, comentarios y docstrings en español.
- Identificadores de código y esquema en inglés técnico.
- Tablas y columnas en `snake_case`; tablas plurales; PK ULID `TEXT`.
- Fechas UTC con zona horaria explícita.
- Enums pequeños con `CHECK`/Python `StrEnum`; catálogos en tablas.
- Sin código muerto, sin duplicación, sin dependencias innecesarias.
- SOLID, DRY, KISS, YAGNI, OWASP, Ley de Hick y Lean UX.
- Diseño editorial sobrio: papel cálido, tinta, verde profundo, sin gradientes ni colores “IA”.

## Comandos

```bash
uv sync --all-groups
uv run patchright install chromium
make dev        # panel en http://127.0.0.1:8765
make worker     # procesa la cola
make test
make lint
make typecheck
make check      # obligatorio antes de cerrar cualquier cambio
make migrate
make seed
make login
make doctor     # diagnóstico local + ping de Gemini
make rescore    # recalcula afinidad sin consultar LinkedIn
```

## Flujo de trabajo

1. Leer `docs/arquitectura.md` y los ADRs relevantes.
2. Cambiar código con tests.
3. Actualizar documentación y, si cambia una decisión, agregar un ADR.
4. Ejecutar `make check`.
5. No commitear salvo pedido explícito.
6. Si se toca LinkedIn, revisar `.agent/skills/postulacion-responsable/SKILL.md`.
7. Si se toca base de datos, ejecutar migración, seed y test.
8. Si se toca UI, revisar accesibilidad, contraste y carga cognitiva.

## Estado actual

La versión 0.1 es local-first. El despliegue remoto está documentado como futuro, no implementado. La automatización de envío está en modo asistido y dry-run por defecto.
