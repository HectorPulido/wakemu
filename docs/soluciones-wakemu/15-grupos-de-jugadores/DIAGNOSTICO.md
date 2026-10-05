# Diagnóstico — 15

## Contexto registrado

**Pendiente:** `COMBAT_GROUPS` administra grupos de monstruos, no parties de jugadores. No se encontró un flujo integrado de invitación, liderazgo y miembros.

**Posible solución:** entidad party independiente y su protocolo de invitación, salida, expulsión y desconexión; integrarla con chat y combate. **Validación:** liderazgo transferido y miembros coherentes tras salir o reconectar.

## Lectura actual

La sección social serializada no es por sí sola un servicio de grupos con invitaciones y membresía. Hace falta una autoridad común para chat, combate y reconexión.

El contexto anterior conserva la evidencia del informe; puede describir una instancia o snapshot anterior. El [cotejo](COTEJO.md) identifica el código leído hoy y sus límites.

## Qué falta para confirmar el recorrido

- OpCodes/snapshots nativos y máximo de miembros.
- Regla de líder, offline y persistencia.
- Relación con compañeros/hero system y futuras guilds.

## Evidencia de origen

[Informe completo](../../reports/auditoria-problemas-wakemu-2026-10-04.md). No se copian capturas privadas, bases, credenciales ni archivos del cliente.
