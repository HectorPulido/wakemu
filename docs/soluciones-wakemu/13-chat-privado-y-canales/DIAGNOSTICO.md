# Diagnóstico — 13

## Contexto registrado

**Confirmado:** el handler `12366` extrae texto y usa `WORLD.broadcast` con `wire.chat`; no implementa selección de canal ni resolución de destinatario privado. `characters/social.py` inicializa listas vacías, no un servicio de mensajería.

**Posible solución:** decodificar solicitudes específicas y enrutar por destinatario, proximidad, grupo o canal, con respuestas de error. **Validación:** tres clientes y comprobación de quién recibe cada mensaje; un privado no debe difundirse.

## Lectura actual

La difusión espacial existente puede servir para canales locales, pero no define destinatario privado ni alcance de gremio/grupo. Validar sesión, membresía y canal antes del envío.

El contexto anterior conserva la evidencia del informe; puede describir una instancia o snapshot anterior. El [cotejo](COTEJO.md) identifica el código leído hoy y sus límites.

## Qué falta para confirmar el recorrido

- Lista priorizada de canales y captura binaria de cada solicitud.
- Regla de offline/ignorados, eco y alcance local.
- Canales de guild/nación que requieren sistemas todavía ausentes.

## Evidencia de origen

[Informe completo](../../reports/auditoria-problemas-wakemu-2026-10-04.md). No se copian capturas privadas, bases, credenciales ni archivos del cliente.
