# Diagnóstico — 25

## Contexto registrado

**Pendiente:** no se encontró una implementación específica integrada de brechas, objetivos, oleadas y recompensa. Teleporters y transporte genérico no acreditan esa función.

**Posible solución:** inventariar los accesos y acciones concretas; separar entrada a instancia de reglas internas, grupos, temporizador y cierre. **Validación:** entrada/salida y progreso con dos jugadores, abandono y recompensas idempotentes.

## Lectura actual

La interacción está restringida a tipos de transporte soportados. Ese resolver no ejecuta una sesión de brecha con oleadas, tiempos y recompensas; no clasificar una brecha como un simple teletransporte.

El contexto anterior conserva la evidencia del informe; puede describir una instancia o snapshot anterior. El [cotejo](COTEJO.md) identifica el código leído hoy y sus límites.

## Qué falta para confirmar el recorrido

- Brecha específica (mapa,objeto,acción) y protocolo completo.
- Reglas de temporizador, oleadas, niveles, recompensas y pausa.
- Destinos/geometry de instancia y política de rejoin.

## Evidencia de origen

[Informe completo](../../reports/auditoria-problemas-wakemu-2026-10-04.md). No se copian capturas privadas, bases, credenciales ni archivos del cliente.
