# Diagnóstico — 30

## Contexto registrado

**Confirmado parcialmente:** `world_static.py` avisa que `13984` actualiza objetos existentes y no crea los ausentes. Su dispatcher no resuelve mesas de oficio; tener una fila en un catálogo no prueba que el cliente cargue la entidad.

**Posible solución:** comprobar mapa y objeto, recurso visual y orden de carga, después implementar interacción, receta, consumo, resultado y XP. **Validación:** la mesa aparece y funciona para dos clientes; ingredientes/resultados se conservan correctamente.

## Lectura actual

Persistir nivel de oficio no implementa recetas ni mesas. Distinguir spawn del interactivo, carrier de apertura y transacción de fabricación; la mesa portable del merkasaco tampoco demuestra crafting completo.

El contexto anterior conserva la evidencia del informe; puede describir una instancia o snapshot anterior. El [cotejo](COTEJO.md) identifica el código leído hoy y sus límites.

## Qué falta para confirmar el recorrido

- Mesa específica/mapa/ID/template y carga de entorno.
- Catálogo de recetas, ingredientes, cantidades, efectos y XP.
- Protocolo de UI crafting/taller y políticas de batch/ocupación.

## Evidencia de origen

[Informe completo](../../reports/auditoria-problemas-wakemu-2026-10-04.md). No se copian capturas privadas, bases, credenciales ni archivos del cliente.
