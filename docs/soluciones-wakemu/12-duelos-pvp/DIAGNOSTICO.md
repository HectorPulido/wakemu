# Diagnóstico — 12

## Contexto registrado

**Confirmado en la ruta revisada:** el inicio de combate resuelve el objetivo mediante `combat_group_for_target`, que busca miembros de grupos NPC disponibles. No se observó una ruta completa de desafío PvP.

**Posible solución:** separar desafío consensuado de ataque a NPC; coordinar aceptación, equipos, colocación, control, abandono y resultado. Definir las recompensas de duelo. **Validación:** ambos clientes comparten un único combate y salen correctamente.

## Lectura actual

Decodificar entrada a un combate no implementa invitación/aceptación de duelo. El PvP debe crear dos equipos de jugadores y definir recompensas separadas.

El contexto anterior conserva la evidencia del informe; puede describir una instancia o snapshot anterior. El [cotejo](COTEJO.md) identifica el código leído hoy y sus límites.

## Qué falta para confirmar el recorrido

- OpCodes nativos del desafío y respuestas.
- Reglas de HP/muerte/XP/kamas en duelo.
- Política de desconexión y multi-control de compañeros.

## Evidencia de origen

[Informe completo](../../reports/auditoria-problemas-wakemu-2026-10-04.md). No se copian capturas privadas, bases, credenciales ni archivos del cliente.
