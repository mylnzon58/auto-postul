# Contexto del producto

AutoPostul nace para que un profesional pueda postularse a ofertas simples de LinkedIn sin repetir formularios, pero sin mentir ni automatizar a ciegas.

## Perfil objetivo inicial

El caso de uso inicial es un perfil híbrido de AI Product Engineer, Full Stack
Developer y especialista en Google Ads Search, con foco en producto, growth,
analítica (GA4, GTM, Hotjar, Clarity), automatización con IA y MCP. El sistema
no debe asumir ese perfil: todo sale del CV importado y de las respuestas
verificadas por el usuario.

## Objetivo

1. Importar el CV sin modificarlo.
2. Entender el perfil y normalizar skills.
3. Buscar ofertas Easy Apply alineadas.
4. Puntuar afinidad 0–100 con evidencia.
5. Preparar el formulario y detenerse en revisión.
6. Enviar solo con confirmación explícita.
7. Auditar todo en local.

## No objetivos de la v1

- Modificar o reescribir el CV automáticamente.
- Postular a ofertas externas.
- Enviar mensajes o invitaciones.
- Scraping masivo.
- Despliegue serverless del worker de navegador.
- Multi-usuario en la nube.

## Principios

- La verdad del CV manda.
- La decisión final es humana.
- La app explica sus scores.
- Los datos quedan locales por defecto.
- El modo seguro es el default.
