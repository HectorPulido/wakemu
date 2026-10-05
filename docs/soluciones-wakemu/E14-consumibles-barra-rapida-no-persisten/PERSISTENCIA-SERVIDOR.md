# E14 — Persistencia concreta de accesos WORLD

## Identidad y esquema propuesto

La evidencia de `cnE/yu/fyt` distingue tipo 1 **USABLE_REFERENCE_ITEM** (long se normaliza a referencia) de tipo 2 **ITEM** (long conserva UID). Guardar el descriptor completo, no solo icono o referencia.

Tabla propuesta `character_world_shortcuts`: `character_id`, `bar_index`, `slot_index`, `descriptor_type`, `descriptor_long`, `descriptor_reference`, `descriptor_extra`, `revision`; PK `(character_id,bar_index,slot_index)` y FK al personaje. Validar barras WORLD y slots con límites nativos acreditados; no aceptar valores por caber en byte. La auditoría actual cubre WORLD, no barras de combate/SYMB ni hechizos.

## Aplicación de 12091

Validar lease y que el i64 del cuerpo corresponda al personaje de la conexión. Decodificar contadores y claves sin aceptar bytes sobrantes; validar todos los descriptores antes de mutar. Aplicar eliminaciones/asignaciones en una transacción, manteniendo revisión de estado en el servidor. Repetir el mismo lote debe dejar el mismo estado; ninguna operación concede o consume inventario.

Para tipo ITEM comprobar propiedad del UID y tipo utilizable según catálogo. Para tipo USABLE_REFERENCE_ITEM comprobar referencia y capacidad de uso; no exigir UID individual ni reescribir su identidad al dividir pila. Las reglas para referencia sin existencias requieren cotejo del consumidor: no borrar automáticamente el acceso al agotar la última unidad sin verificarlo.

## Restauración y cambios de inventario

Restaurar mediante la colección nativa `so/sq/yw/yu`, ya probada, no mediante una lista JSON ni el cuerpo de solicitud 12091. Incluir barras vacías anteriores si hacen falta para preservar índices relativos: el consumidor completo limpia barras ausentes. Ordenar barras/slots de forma determinista y construir un snapshot consistente tras commit antes de publicarlo.

Un acceso tipo ITEM cuya entidad desaparezca por consumo/transferencia debe resolverse según la política nativa acreditada; nunca enlazarlo a un UID ajeno reciclado. No convertirlo silenciosamente a tipo referencia. Mantener restauración separada del refresco de cantidad de inventario del issue 1.

## Validación pendiente

Capturar asignación real y momento de envío de 12091, reconectar, restaurar dos barras incluyendo una vacía, dividir/consumir pila, borrar/transferir UID, personaje distinto y lote inválido sin aplicación parcial. Probar reapertura de DB y dos sesiones para verificar lease y estado durable. Los fixtures acreditan codec/consumidor, no estas operaciones reales. No se implementó tabla ni handler.
