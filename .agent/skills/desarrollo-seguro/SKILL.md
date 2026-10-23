---
name: desarrollo-seguro
description: Usar cuando se toquen formularios, autenticación, archivos, secretos, red, base de datos o cualquier superficie web de AutoPostul. Aplica OWASP y privacidad local.
---

# Desarrollo seguro

- Bind solo a `127.0.0.1` por defecto.
- CSRF en todos los POST.
- Cookies `SameSite=Strict`; `https_only` solo en despliegue con TLS.
- Autoescape de Jinja activo; nunca `innerHTML` con datos del usuario.
- CSP y headers de seguridad.
- Validar tipo, tamaño y nombre de archivos subidos.
- Guardar archivos fuera del árbol web; nombres aleatorios o hash.
- No loguear CV, teléfono, email, cookies ni claves.
- Secretos en `.env` o llavero; nunca en Git.
- Consultas por ORM; nada de SQL concatenado.
- URLs externas no se abren automáticamente.
- Ante CAPTCHA/2FA/checkpoint: detenerse.
- Si se agrega una dependencia: fijarla y ejecutar `pip-audit`.
