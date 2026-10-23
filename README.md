# AutoPostul

Asistente local para descubrir ofertas **Easy Apply** de LinkedIn, medir afinidad con tu CV y preparar el formulario de postulación. Nada se envía sin tu confirmación.

> Estado: `0.1.0` local-first. El worker de navegador corre en tu equipo. El despliegue remoto está documentado, no implementado.

## Qué problema resuelve

Buscar trabajo en LinkedIn implica repetir filtros, leer decenas de ofertas y completar formularios casi idénticos. AutoPostul ordena ese trabajo:

1. Importa el CV sin modificarlo.
2. Normaliza el perfil y las skills.
3. Busca ofertas Easy Apply.
4. Calcula una afinidad explicable de 0 a 100.
5. Completa el formulario.
6. Permite varios perfiles, cada uno con su CV, respuestas y búsquedas.
7. Se detiene en revisión.
8. Envía solo si escribís `ENVIAR`.

## Qué no hace

- No modifica ni reescribe tu CV.
- No inventa experiencia, skills, fechas ni respuestas.
- No postula a ofertas externas.
- No envía mensajes ni invitaciones.
- No evade CAPTCHA, 2FA, checkpoints ni rate limits.
- No hace scraping masivo.

## Stack

- Python 3.13 + uv
- FastAPI + Jinja2 + HTMX vendorizado + CSS puro
- SQLAlchemy 2 + Alembic + SQLite WAL
- Patchright para Easy Apply
- `mcp-server-linkedin` pinneado para lectura
- Google AI Studio / Gemini

## Requisitos

- macOS, Linux o Windows con Python 3.12.4–3.14.
- `uv`.
- Una cuenta de LinkedIn.
- Una API key de Google AI Studio (opcional para probar; recomendada para extracción y redacción).
- Chromium administrado por Patchright.

## Instalación

```bash
git clone https://github.com/mylnzon58/auto-postul.git
cd auto-postul
cp .env.example .env
# completar GEMINI_API_KEY y SESSION_SECRET
make setup
make migrate
make seed
make login
make dev
```

Abrí <http://127.0.0.1:8765>.

En otra terminal:

```bash
make worker
```

El worker procesa escaneos, preparaciones y envíos. La UI solo encola; el navegador pertenece al worker.

## Uso mínimo

1. **Perfil y CV**: importá el PDF. Revisá identidad, skills y experiencias.
2. **Banco de respuestas**: marcá como verificadas solo las respuestas que confirmás.
3. **Ajustes**: abrí el login de LinkedIn y completá el acceso en la ventana visible.
4. **Búsquedas**: revisá o creá perfiles de búsqueda.
5. **Resumen**: ejecutá un escaneo.
6. **Ofertas**: mirá el termómetro, la evidencia y los faltantes.
7. **Preparar**: el worker abre Easy Apply y completa el formulario.
8. **Revisión**: revisá cada campo.
9. **Enviar**: escribí `ENVIAR`. En modo seguro no se envía nada.

## Configuración

Copiá `.env.example` a `.env`. Los valores importantes:

```dotenv
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-2.5-flash
APPLY_DRY_RUN=true
APPLY_LIVE_SUBMIT=false
DAILY_SCAN_LIMIT=1
DAILY_JOB_DETAIL_LIMIT=25
DAILY_APPLY_LIMIT=5
```

Para un envío real, en tu equipo y con tu confirmación:

```dotenv
APPLY_DRY_RUN=false
APPLY_LIVE_SUBMIT=true
```

No commitees `.env`.

## Comandos

```bash
make setup      # dependencias + Chromium
make dev        # panel local
make worker     # cola de automatización
make login      # login visible de LinkedIn
make migrate    # migraciones Alembic
make seed       # skills, respuestas y búsquedas iniciales
make test       # pytest
make lint       # ruff
make typecheck  # mypy
make check      # lint + tipos + tests
```

## Arquitectura en una imagen

```text
CV PDF original
      │
      ▼
Ingesta local + Gemini ──► Perfil canónico revisado
                                  │
                                  ▼
LinkedIn MCP ──► Ofertas normalizadas ──► Rúbrica de afinidad
                                                  │
                                                  ▼
                                        Cola SQLite
                                                  │
                                                  ▼
                                  Patchright / Easy Apply
                                                  │
                                                  ▼
                                     Revisión humana
                                                  │
                                          ENVIAR │
                                                  ▼
                                    Auditoría + capturas
```

El MCP **lee** LinkedIn. No tiene herramienta para postularse. Por eso el envío asistido usa Patchright sobre el mismo perfil de navegador, con un lock para que nunca corran a la vez.

## Privacidad

- Datos en el directorio de usuario del sistema, fuera del repo.
- CV original inmutable.
- Sin cookies ni contraseñas en SQLite.
- Gemini recibe el texto necesario para estructurar CV/ofertas. Si no querés eso, dejá `GEMINI_API_KEY` vacío y la app usa reglas locales.
- Logs sin secretos.

Directorio por defecto:

- macOS: `~/Library/Application Support/AutoPostul`
- Linux: `~/.local/share/AutoPostul`
- Windows: `%LOCALAPPDATA%\AutoPostul`

## Seguridad y riesgo

Este proyecto automatiza una cuenta real. LinkedIn no autoriza oficialmente este tipo de automatización. El modo asistido, los límites bajos y el freno ante CAPTCHA reducen el riesgo, pero no lo eliminan. La cuenta y la decisión de uso son tuyas.

Leé [`docs/seguridad.md`](docs/seguridad.md) antes de habilitar el envío live.

## Documentación

- [`docs/arquitectura.md`](docs/arquitectura.md)
- [`docs/flujos.md`](docs/flujos.md)
- [`docs/modelo-datos.md`](docs/modelo-datos.md)
- [`docs/seguridad.md`](docs/seguridad.md)
- [`docs/operacion.md`](docs/operacion.md)
- [`docs/despliegue-futuro.md`](docs/despliegue-futuro.md)
- [`docs/decisiones/`](docs/decisiones/)

## Licencia

MIT. El servidor MCP de LinkedIn es Apache-2.0 y se usa como dependencia. Ver [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
