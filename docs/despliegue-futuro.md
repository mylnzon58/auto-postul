# Despliegue futuro

La v1 es local-first. Este documento describe opciones para una etapa posterior. No hay código de despliegue implementado.

## Restricción principal

El worker de postulación necesita:

- Chromium persistente;
- perfil de LinkedIn con login interactivo;
- ventana visible para CAPTCHA/2FA y revisión;
- IP estable;
- almacenamiento de capturas.

Ese worker **no** debe ir a Vercel Functions ni Cloudflare Workers. El panel de solo lectura sí puede desplegarse.

## Opción A: VPS + Postgres

```text
VPS con Chromium + worker + panel
        │
        ├── Postgres gestionado o local
        └── S3/R2 para artefactos
```

Ventajas: control total, IP fija, navegador headed. Desventajas: mantenimiento, backups, TLS y autenticación propia.

Pasos:

1. Agregar adaptador Postgres a `db/session.py`.
2. Mover artefactos a un `ArtifactStore` S3/R2.
3. Agregar auth OIDC o contraseña fuerte.
4. Configurar TLS y proxy inverso.
5. Migrar con Alembic.
6. Mantener el worker en el VPS, no en serverless.

## Opción B: Vercel + Supabase

```text
Vercel: panel read-only / API
Supabase: Postgres + Auth + Storage
VPS: worker de navegador
```

Ventajas: panel rápido, auth y backups gestionados. Desventajas: dos despliegues, CORS, latencia y costos.

Supabase ya está disponible en el entorno del autor, pero no se usa en v1. Si se adopta, aplicar RLS por usuario y no exponer la service role key al frontend.

## Opción C: Cloudflare + D1/R2

```text
Cloudflare Pages/Workers: panel y API
D1: SQLite gestionado
R2: artefactos
VPS: worker de navegador
```

D1 es SQLite-compatible, pero no es un reemplazo directo de SQLAlchemy/SQLite local. Requiere adaptador HTTP o un ORM compatible. R2 es buen destino para capturas. Workers no ejecutan Chromium.

## Qué mantener portable

- IDs ULID.
- Fechas UTC.
- Repositorios y puertos en `application`.
- `ArtifactStore` y `Queue` como interfaces.
- Sin SQL específico de SQLite en dominio.
- Migraciones Alembic.
- Configuración por entorno.

## No hacer todavía

- Multi-tenant real.
- Suscripciones o pagos.
- Automatización de ofertas externas.
- Envío desatendido masivo.
- Sincronización de sesión de LinkedIn entre dispositivos.
