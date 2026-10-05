# Diagnóstico — E09

## Contexto registrado

Probe sobre checkout con SQLite temporal/MemoryRedis: cargas con hit repiten9SELECT,3INSERT idempotentes y7CREATEIFNOTEXISTS; save usa20SELECT y2UPDATE. No prueba20s de latencia. Journal20min se comprobó, pero no equivale a lectura Redis primero.

## Lectura actual

Las lecturas de progreso, merkasaco, inventario y builds preceden al overlay. El hit del journal no evita esta hidratación SQL; mover DDL tampoco elimina por sí solo SELECT redundantes.

El contexto anterior conserva la evidencia del informe; puede describir una instancia o snapshot anterior. El [cotejo](COTEJO.md) identifica el código leído hoy y sus límites.

## Qué falta para confirmar el recorrido

- Contrato completo de snapshot y qué lecturas deben seguir inmediatas.
- Todos los writers y su mecanismo invalidation/version.
- Carga y latencia del Redis realmente desplegado.

## Evidencia de origen

[Informe completo](../../reports/auditoria-problemas-wakemu-2026-10-04.md). No se copian capturas privadas, bases, credenciales ni archivos del cliente.
