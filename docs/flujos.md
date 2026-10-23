# Flujos

## 1. Onboarding

```text
CV PDF → copia inmutable → texto → Gemini/heurística → perfil revisable
```

- El PDF nunca se mueve ni se edita.
- El usuario corrige identidad, skills, experiencias y respuestas.
- Se crean búsquedas iniciales según el perfil.
- Se muestra el estado de la sesión de LinkedIn y de Gemini.

## 2. Escaneo

```text
búsquedas activas → MCP search_jobs → deduplicar → detalles → apply URL → normalizar → score
```

- Solo ofertas Easy Apply.
- Límite diario de ofertas.
- No crea postulaciones.
- Si el MCP falla, la tarea registra el error y no inventa datos.
- Si una oferta ya existe, no se vuelve a leer.

## 3. Preparación

```text
job_id → verificar oferta → abrir Patchright → Easy Apply → leer campos → resolver
→ completar → siguiente → revisión → guardar campos y captura
```

- Respuestas desde perfil y banco verificado.
- Campo obligatorio desconocido → `needs_input`; no se adivina.
- Error de validación → se detiene y muestra el error.
- Nunca hace clic en enviar.

## 4. Envío

```text
ready_for_review → usuario escribe ENVIAR → worker → click submit → verificar → auditar
```

- Si `APPLY_DRY_RUN=true` o `APPLY_LIVE_SUBMIT=false`, no se envía.
- Si la confirmación es ambigua, `submission_unknown`; no se reintenta.
- Si LinkedIn confirma, `submitted` y se guarda la captura.

## 5. Errores

| Situación | Acción |
|---|---|
| CAPTCHA / 2FA / checkpoint | detenerse y avisar |
| Rate limit | pausar y no reintentar en loop |
| Layout desconocido | `needs_input`, captura, revisión manual |
| Oferta cerrada | `closed`, no preparar |
| Ya aplicada | `applied`, no preparar |
| Envío ambiguo | `submission_unknown`, no reintentar |
| Sesión vencida | pedir login de nuevo |

## 6. Estados de postulación

```text
detected → scored → shortlisted → preparing → needs_input
                                              ↘ ready_for_review → submitting
                                                                    ├─ submitted
                                                                    ├─ failed
                                                                    └─ submission_unknown
```
