# Operación

## Arranque

```bash
make dev
make worker
```

El panel queda en `http://127.0.0.1:8765`. El worker debe estar corriendo para escanear, preparar y enviar.

## Primera vez

```bash
make setup
make migrate
make seed
make login
```

`make login` abre una ventana de Chromium. Completá LinkedIn, incluido 2FA o CAPTCHA si aparece. No cierres la ventana hasta que termine.

## Datos

- Base: `<APP_DATA_DIR>/auto_postul.sqlite`
- CVs copiados: `<APP_DATA_DIR>/documents/`
- Capturas: `<APP_DATA_DIR>/artifacts/`
- Logs: `<APP_DATA_DIR>/logs/`
- Perfil LinkedIn: `<APP_DATA_DIR>/linkedin/profile/`

## Backup

Con la app y el worker detenidos:

```bash
cp "$HOME/Library/Application Support/AutoPostul/auto_postul.sqlite" ./backup-auto-postul.sqlite
```

En Linux/Windows, usá la ruta correspondiente de `platformdirs`.

## Diagnóstico

1. `/api/health` debe devolver `ok: true`.
2. `Ajustes` muestra sesión de LinkedIn, Gemini y tareas activas.
3. `Actividad` muestra errores de worker.
4. Si el MCP no arranca, verificá `uvx --version`.
5. Si Chromium no existe: `make browser`.

## Cambiar modo de envío

Editar `.env`:

```dotenv
APPLY_DRY_RUN=false
APPLY_LIVE_SUBMIT=true
```

Reiniciar worker. La UI seguirá pidiendo `ENVIAR`.

## Limpiar datos

Detener app y worker. Eliminar el directorio de datos. No hay comando destructivo automático en la app.

## Actualizar MCP

1. Cambiar `LINKEDIN_MCP_VERSION` en `.env`.
2. Ejecutar un escaneo de prueba.
3. Revisar que `search_jobs`, `get_job_details` y `get_job_apply_url` sigan funcionando.
4. Si cambia el formato, actualizar `domain/jobs.py` y sus tests.
