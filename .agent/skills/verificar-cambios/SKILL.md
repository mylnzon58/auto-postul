---
name: verificar-cambios
description: Usar SIEMPRE al terminar cualquier cambio de código, migración, template o configuración en AutoPostul. Verifica lint, tipos, tests, migraciones y reglas de seguridad.
---

# Verificar cambios

1. Ejecutar `make check`.
2. Si se tocó el esquema, ejecutar `make migrate` y `make seed` sobre una base limpia y verificar el arranque.
3. Si se tocó la UI, abrir el panel y revisar:
   - foco visible;
   - contraste;
   - navegación por teclado;
   - que el termómetro muestre número y etiqueta;
   - que no haya gradientes ni colores “IA”.
4. Si se tocó LinkedIn, revisar que:
   - `APPLY_DRY_RUN` siga en `true` por defecto;
   - no se envíe nada sin `ENVIAR`;
   - se frene ante CAPTCHA, 2FA o rate limit;
   - no se reintente un envío ambiguo.
5. Revisar `git diff --stat` y `git status` para detectar PII, PDFs, `.env` o bases.
6. Reportar el resultado real de los comandos. No decir “listo” si `make check` falla.
