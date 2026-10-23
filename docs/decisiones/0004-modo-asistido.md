# ADR 0004: modo asistido y dry-run por defecto

- Fecha: 2026-10-23
- Estado: aceptado

## Contexto

Enviar postulaciones es una acción irreversible. LinkedIn puede restringir cuentas automatizadas. El usuario quiere completar todo el formulario, pero decidir el envío.

## Decisión

- `APPLY_DRY_RUN=true` y `APPLY_LIVE_SUBMIT=false` por defecto.
- La preparación completa el formulario y se detiene en revisión.
- El envío exige escribir `ENVIAR`.
- Un resultado ambiguo se marca `submission_unknown` y no se reintenta.
- CAPTCHA, 2FA, checkpoint o rate limit detienen la automatización.

## Consecuencias

- Más pasos manuales.
- Menor riesgo de envíos accidentales o duplicados.
- La UI debe mostrar claramente el modo seguro y el estado de cada postulación.
