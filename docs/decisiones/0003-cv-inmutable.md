# ADR 0003: CV original inmutable

- Fecha: 2026-10-23
- Estado: aceptado

## Contexto

El usuario no quiere que el sistema reescriba su CV ni invente experiencia para pasar filtros. La app puede sugerir mejoras, pero la decisión es humana.

## Decisión

- El PDF original se copia tal cual y se guarda con hash.
- La extracción produce datos revisables.
- No hay reescritura automática.
- Las respuestas de formularios salen del perfil y de un banco verificado.
- Si falta un dato obligatorio, la preparación se detiene.

## Consecuencias

- Menos “optimización” automática.
- Más integridad y menos riesgo de mentir en una entrevista.
- La UI debe hacer visible qué dato falta y por qué.
