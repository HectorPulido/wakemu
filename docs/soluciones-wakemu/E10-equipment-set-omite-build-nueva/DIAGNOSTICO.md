# Diagnóstico — E10

## Contexto registrado

Prueba de frontera: equipment_set sustituye registros existentes pero no incorpora índice2 si el conjunto de entrada solo contenía0. Bootstrap y update no son automáticamente equivalentes; se confirmó por bytes en el probe de límites, no por creación gráfica completa.

## Lectura actual

Itera campos existentes y sustituye equipo cuando encuentra un índice guardado. No añade entradas para nuevos índices ausentes del original. Diferenciar refresh completo, update y registro de creación.

El contexto anterior conserva la evidencia del informe; puede describir una instancia o snapshot anterior. El [cotejo](COTEJO.md) identifica el código leído hoy y sus límites.

## Qué falta para confirmar el recorrido

- Handler/merge exacto y carrier para insertar frente a sustituir.
- Fixture de creación gráfica que use esa ruta específica.
- Política de completar todas las colecciones ante add/delete.

## Evidencia de origen

[Informe completo](../../reports/auditoria-problemas-wakemu-2026-10-04.md). No se copian capturas privadas, bases, credenciales ni archivos del cliente.
