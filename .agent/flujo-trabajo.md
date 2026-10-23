# Flujo de trabajo

## Antes de cambiar

1. Identificar la capa afectada: dominio, aplicación, infraestructura, web, worker o datos.
2. Leer el ADR o documento relevante.
3. Si el cambio toca LinkedIn, leer el skill `postulacion-responsable`.

## Durante

- Escribir el test primero cuando sea posible.
- Mantener el dominio puro.
- No duplicar reglas de negocio en templates.
- No agregar una dependencia sin justificar y fijar versión.
- Si se cambia el esquema: migración, seed y test.

## Después de cada cambio

Ejecutar siempre:

```bash
make check
```

Ese comando corre lint, formato, tipos y tests. Si falla, no se cierra la tarea.

Además:

- Actualizar `README.md` si cambia el uso.
- Actualizar `docs/` si cambia arquitectura o flujo.
- Agregar ADR si se cambia una decisión estructural.
- Verificar que no se agregó PII ni secretos al repo.
- Revisar que el modo seguro siga siendo el default.

## Cierre de etapa

Una etapa se considera terminada solo si:

- El flujo funciona de punta a punta.
- Hay tests.
- `make check` pasa.
- La documentación está actualizada.
- No hay código muerto ni placeholders sin explicar.
