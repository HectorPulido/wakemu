# Revisión de respuestas — bolso Sadida apilado

## Referencia resuelta y prueba actual

El bolso Sadida negro es **12493**: capacidad10, nivel mínimo1, sin filtros de tipos y sin criterio adicional de equipación en `inventory-bag-rules.json`. `ordinary(12493)` lo acepta. Por tanto, para este objeto no falta decidir soporte de bolso especializado: el bloqueo actual es la cantidad del stack o la ocupación del slot.

Se ejecutaron tres casos con cuentas/personajes nuevos en SQLite desechable y el servicio actual:

| Caso | Resultado | Persistencia al reabrir |
| --- | --- | --- |
| Cantidad3, slot2 libre | Rechazo antes de modificar; recuperación13713 de74 bytes | Las tres unidades y ambos contenedores intactos |
| Cantidad1, slot2 libre | Éxito, respuestas12470 y12919 | UID convertido en bolso de10 celdas, sin ítem duplicado |
| Cantidad1, slot1 ocupado por bolso inicial | Rechazo por reemplazo no implementado; misma recuperación13713 | Unidad y contenedores intactos |

Los tres tests actuales de `test_inventory_bags.py` también pasan. [Estados, límites y hashes](probe-sadida-stack-actual.json). Estas pruebas no vuelven a reproducir la pantalla negra: cotejan el estado persistente actual con el fallo nativo registrado previamente.

## Dos fallos diferentes

`equip` exige `quantity == 1` y rechaza el stack antes de llamar a `ordinary`. El dispatcher atrapa ese `ValueError` y envía `inventory_move.synchronization`: i64 personaje seguido únicamente de `bags(character)`. `cwY.dp` acepta cualquier resto después del ID; **que ese parser devuelva true no valida el contenido**. `chK` entrega ese resto a `biB.as`, lector de entidad completa. La reproducción previa registró `BufferUnderflowException` en esa ruta y corrupción de vistas; el constructor actual conserva el mismo contrato incorrecto.

No se encontró evidencia de pérdida de las unidades en los casos SQLite ni de que el valor visual INT32_MAX de PdV sea una vida persistida. El reinicio vuelve a cargar otra serialización, lo que concuerda con recuperación visual sin arreglar la causa.

El alcance supera el Sadida: el mismo constructor se usa ante rechazo de equipar/quitar bolso, consumir, destruir y mover objetos. Un bolso de una unidad en slot ocupado alcanza la misma respuesta peligrosa. Además, la rama de bolsos usa `character` cacheado, mientras otras ramas recargan `STORE.character`: la recuperación debe partir siempre de estado autoritativo posterior al rollback y lease vigente.

## Solución concreta y orden

Primero sustituir **todos** los usos de la recuperación inválida. `wire.minimal_entity` es un adaptador de fixtures verificados, no un serializer general: no presentar `bags`, `minimal_entity` o un byte de formato inventado como solución terminada. Construir una entidad completa con secciones y formato acreditados para13713, o demostrar otro carrier nativo de recuperación de inventario; probar el consumidor sobre una entidad ya cargada y su relación con la mutación optimista. Esto sigue pendiente y requiere prueba nativa/GUI; no basta validar `cwY.dp`.

Después implementar split de una unidad dentro de la transacción de equipación. Mantener el UID original del stack restante y reservar un UID exclusivo para el nuevo contenedor. Registrar operación/UIDs/estado previo para que una repetición no equipe otra unidad; conservar cantidades y propiedades. No necesitar un slot provisional de inventario cuando el destino final es directamente el slot de bolso. Para una unidad, conservar el UID actual como hoy. Confirmar antes de anunciar el nuevo contenedor y cotejar12470/12919 con el estado optimista real para evitar doble decremento.

El reemplazo debe conservar el UID y los contenidos del bolso retirado; nunca trasladar implícitamente su contenido al nuevo de menor capacidad. Falta cotejar la solicitud nativa de swap y si el cliente permite retirarlo con contenido. Hasta acreditarlo, mantener rechazo seguro sin modificar nada; la decisión no corresponde al usuario ni autoriza inventar una transferencia automática. Especializados requieren evaluación de filtros/criterios aparte y no bloquean12493.

## Pendientes de reproducción

Stack2/3 en GUI con recuperación válida, slot ocupado y destino lleno, doble solicitud, desconexión tras commit, swap con contenido y capacidad menor, Redis y recompensas que entregan bolsos. Verificar inventario, mundo, ficha y HUD juntos. No se aplicaron fixes ni cambios del cliente.
