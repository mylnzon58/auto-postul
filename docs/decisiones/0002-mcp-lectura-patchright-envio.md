# ADR 0002: MCP para lectura, Patchright para Easy Apply

- Fecha: 2026-10-23
- Estado: aceptado

## Contexto

`stickerdaniel/linkedin-mcp-server` expone búsqueda, detalle, perfiles, empresas y `get_job_apply_url`. No expone una herramienta para completar o enviar una postulación. `get_job_apply_url` solo clasifica `easy_apply`, `external`, `applied` o `closed`.

## Decisión

- MCP pinneado para descubrimiento y lectura.
- Patchright para el formulario Easy Apply.
- Ambos comparten el perfil de navegador, con acceso secuencial.
- No se bifurca el MCP en v1.

## Consecuencias

- Una sola sesión de LinkedIn.
- El worker debe cerrar el MCP antes de abrir Patchright.
- Si el worker se reinicia, la sesión de revisión se pierde y hay que preparar de nuevo.
- Si el MCP agrega apply en el futuro, se puede reemplazar el adaptador de envío sin tocar el dominio.
