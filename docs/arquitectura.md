# Arquitectura

## Decisión principal

AutoPostul es un **monolito modular local-first**. No hay microservicios ni frontend SPA. La UI y el worker comparten SQLite; el worker es el único dueño del navegador.

El repositorio `stickerdaniel/linkedin-mcp-server` se usa para **lectura**. Su herramienta `get_job_apply_url` solo clasifica la oferta; no completa ni envía el formulario. El envío asistido se implementa con Patchright.

## Capas

```text
src/auto_postul/
├── domain/          reglas puras, schemas, scoring, parser, skills
├── application/     casos de uso: importar CV, escanear, preparar, enviar, cola
├── infrastructure/  MCP, Patchright, Gemini, archivos
├── db/              SQLAlchemy, modelos, sesión, seed
├── web/             FastAPI, rutas, templates, CSS, HTMX
└── worker/          consumidor de la cola
```

Reglas de dependencia:

- `domain` no importa FastAPI, SQLAlchemy, Patchright ni Gemini.
- `application` depende de `domain` y de puertos.
- `infrastructure` implementa adaptadores.
- `web` y `worker` son bordes de entrada.

## Flujo de datos

1. El usuario importa un PDF desde la raíz o desde el formulario.
2. `application/cv_import.py` copia el original a `documents/` y extrae texto con pypdf.
3. Gemini puede estructurar el texto; si falla, se usa `domain/cv.py`.
4. El perfil se guarda normalizado.
5. El worker toma una tarea `scan`.
6. `LinkedInMcpClient` llama a `search_jobs`, `get_job_details` y `get_job_apply_url`.
7. `domain/jobs.py` normaliza la oferta.
8. `domain/scoring.py` calcula afinidad con rúbrica versionada.
9. La UI muestra la cola.
10. Una tarea `prepare` abre Patchright, completa Easy Apply y se detiene.
11. La UI muestra campos, fuente y advertencias.
    El adaptador soporta el modal clásico y el flujo actual de página completa `unified-apply`.
12. Una tarea `submit` exige `ENVIAR`, verifica el resultado y audita.

## Sesión de LinkedIn

El MCP y Patchright comparten el perfil en:

```text
<APP_DATA_DIR>/linkedin/profile
```

El MCP rota el perfil y su padre al limpiar sesión. Por eso el perfil vive en un directorio dedicado y la base de datos está fuera de él.

No hay dos navegadores a la vez:

- El worker procesa una tarea por vez.
- El MCP se abre y se cierra dentro de la tarea de escaneo.
- Patchright se abre en la tarea de preparación.
- Una preparación puede quedar abierta para revisión; el envío usa esa misma sesión.

Limitación conocida: si el worker se reinicia entre preparar y enviar, la sesión de revisión se pierde y hay que volver a preparar. El sistema lo informa.

## Auto-postulación

La tarea `auto_apply` selecciona ofertas Easy Apply remotas con score suficiente, las prepara y las envía en secuencia. Usa el mismo `prepare`/`submit` que el flujo manual, con pausas aleatorias y tope diario. No inventa respuestas: si una oferta requiere un dato desconocido, la omite. La configuración vive en `setting` y se edita desde el panel.

## Proceso en vivo

El worker escribe una captura del navegador en `artifacts/live-<application_id>.png` cada dos segundos mientras una preparación está abierta. El panel lee esa captura y sus metadatos, y la muestra embebida en **Proceso**. No hay streaming de video ni WebSocket: es una captura periódica local, suficiente para ver el estado real del navegador.

## Cola

`automation_run` es la cola. Estados: `queued`, `running`, `done`, `failed`.

Un solo worker reclama la tarea más antigua con `claim_next`. No hay Redis. SQLite en WAL y `busy_timeout` cubren el caso local.

## Por qué no serverless en v1

El worker necesita:

- Chromium persistente;
- sesión de LinkedIn;
- ventana visible para login y revisión;
- IP estable;
- archivos y capturas.

Eso no encaja en Vercel Functions ni Cloudflare Workers. El panel de solo lectura sí podría desplegarse; el worker no.

Ver `docs/despliegue-futuro.md`.

## Riesgos técnicos

- El HTML de LinkedIn cambia. Los selectores están aislados en `linkedin_apply.py`.
- El MCP devuelve texto crudo. El parser y Gemini pueden fallar; se guarda `raw_text` y se muestra para revisión.
- La afinidad no es una probabilidad real de contratación.
- Los tests no usan LinkedIn real. Las pruebas live son manuales.
