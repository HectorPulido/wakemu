# Diagnóstico — 29

## Contexto registrado

**Confirmado parcialmente:** `maps/world_static.py::interaction` clasifica puertas/teleporters, pero no ejecuta lógica de mazmorra. La ruta `12870` revisada registra numerosas interacciones y continúa sin resolverlas. `wire.py` vacía progreso heredado de mazmorra; eso no implementa instancias ni salas.

**Posible solución:** accesos, instancia compartida para el grupo, salas/encuentros, progreso, condiciones y salida. **Validación:** entrada con requisitos válidos, dos jugadores en la misma instancia, victoria y abandono sin quedar atrapados.

## Lectura actual

La ruta actual rechaza instancias distintas de 0 y solo soporta determinados transportes. Mazmorras requieren sesiones de instancia, acceso, progresión y recuperación; permitir puertas no completa el sistema.

El contexto anterior conserva la evidencia del informe; puede describir una instancia o snapshot anterior. El [cotejo](COTEJO.md) identifica el código leído hoy y sus límites.

## Qué falta para confirmar el recorrido

- Mazmorra priorizada, mapas/puertas, geometría, llaves y progresión.
- Dificultad/XP/loot, rejoin, lockouts y reset de instancia.
- Protocolo de UI mazmorra, stasis y fin, no solo teleport.

## Evidencia de origen

[Informe completo](../../reports/auditoria-problemas-wakemu-2026-10-04.md). No se copian capturas privadas, bases, credenciales ni archivos del cliente.
