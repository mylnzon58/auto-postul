---
name: postulacion-responsable
description: Usar cuando se modifique el adaptador de LinkedIn, el flujo Easy Apply, el scoring de ofertas o cualquier acción que pueda terminar en una postulación.
---

# Postulación responsable

## Reglas duras

1. El CV original no se modifica.
2. No se inventan datos para “pasar” un filtro.
3. Si falta un campo obligatorio, se detiene y se pide el dato.
4. No se envía nada sin confirmación explícita.
5. No se reintenta un envío cuyo resultado es desconocido.
6. No se evaden CAPTCHA, 2FA, checkpoints ni rate limits.
7. No se envían mensajes, invitaciones ni se hace scraping masivo.
8. Solo Easy Apply en v1.

## Flujo correcto

1. Verificar sesión.
2. Verificar que la oferta siga abierta y no aplicada.
3. Abrir Easy Apply.
4. Completar campos desde perfil y banco de respuestas verificadas.
5. Detenerse en revisión.
6. Confirmar con la palabra `ENVIAR`.
7. Verificar el resultado real.
8. Guardar captura y evento.
9. Si el resultado es ambiguo, marcar `submission_unknown` y no reintentar.

## Pruebas

- Usar HTML sintético para los formularios.
- Nunca enviar en tests.
- Los tests live son manuales y requieren `@pytest.mark.live`.
