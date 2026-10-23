# Seguridad

## Reportar

No abras un issue público con datos personales, cookies, claves o capturas de LinkedIn.

Para reportar un problema de seguridad, contactá al maintainer del repositorio
`mylnzon58/auto-postul` de forma privada.

## Alcance

AutoPostul es una herramienta local. No está pensada para exponerse a internet
sin autenticación, TLS y revisión adicional.

## Buenas prácticas

- Mantener `APP_HOST=127.0.0.1`.
- Usar una contraseña local si el equipo es compartido.
- No commitear `.env` ni PDFs.
- Revisar `.gitignore` antes de `git add`.
- Revocar una API key de Gemini si se filtra.
- Ante CAPTCHA, 2FA o checkpoint, detener la automatización.
