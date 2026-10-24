# Seguridad

## Modelo de amenaza

AutoPostul corre en la máquina del usuario, con su sesión de LinkedIn y su CV. Las amenazas relevantes son:

- exposición del panel a la red local;
- CSRF en formularios;
- robo de secretos en `.env` o logs;
- inyección de HTML en templates;
- subida de archivos maliciosos;
- automatización que envía algo sin confirmación;
- bloqueo de la cuenta por exceso de acciones.

## Controles implementados

- Bind por defecto a `127.0.0.1`.
- Contraseña local opcional (`APP_PASSWORD`).
- CSRF en todos los POST.
- Cookies `SameSite=Strict`.
- CSP, `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`.
- Jinja autoescape.
- Archivos fuera del árbol web.
- Hash SHA-256 de CV y artefactos.
- Logs sin secretos.
- Gemini opcional.
- Modo dry-run por defecto.
- Confirmación literal `ENVIAR`.
- No reintento de envíos ambiguos.
- Límites diarios.
- Freno ante CAPTCHA, 2FA, checkpoint o rate limit.

## Secretos

- `.env` no se commitea.
- La UI nunca muestra la API key.
- Si una clave se filtra, hay que revocarla en Google AI Studio y generar otra.
- No pegar claves en issues, capturas ni chats.

## OWASP Top 10

| Riesgo | Mitigación |
|---|---|
| Control de acceso | localhost, contraseña opcional, sin API pública |
| Fallas criptográficas | TLS solo en despliegue; secretos en entorno |
| Inyección | ORM, Jinja autoescape, CSS/JS sin HTML dinámico |
| Diseño inseguro | confirmación humana, dry-run, límites |
| Configuración insegura | headers, sin debug en producción, permisos |
| Componentes vulnerables | versiones pinneadas, `pip-audit` |
| Autenticación | sesión firmada, CSRF, bloqueo local |
| Integridad | constraints, migraciones, idempotencia |
| Logging | sin PII, auditoría local |
| SSRF | MCP no abre URLs externas; la app no descarga apply URLs |

## Auto-postulación

El modo automático es opt-in y solo corre con `APPLY_LIVE_SUBMIT=true`. Aun así, envía sin revisión individual. Usalo solo con score alto, tope diario bajo, solo remoto y pausas largas. Revisá periódicamente la actividad y detené el worker si LinkedIn muestra señales de alerta.

## LinkedIn

LinkedIn no autoriza oficialmente esta automatización. El diseño reduce el volumen y exige revisión, pero no elimina el riesgo de restricciones de cuenta. No usar para spam, scraping masivo ni evasión de controles.

## Reportar un problema

Abrí un issue privado o contactá al maintainer. No incluyas datos personales, cookies ni claves.
