# ADR 0001: local-first con SQLite

- Fecha: 2026-10-23
- Estado: aceptado

## Contexto

El producto maneja un CV, una sesión de LinkedIn y postulaciones personales. El worker necesita un navegador visible y una IP estable. El autor quiere macOS primero, con soporte futuro para Windows/Linux y despliegue remoto documentado.

## Decisión

La v1 corre localmente. La base es SQLite en WAL. Los datos viven en el directorio de usuario, no en el repo.

## Consecuencias

- Cero infraestructura para empezar.
- Privacidad y backups simples.
- Un solo worker, sin concurrencia distribuida.
- Migrar a Postgres requiere un adaptador, no reescribir el dominio.
- Serverless no es viable para el worker.
