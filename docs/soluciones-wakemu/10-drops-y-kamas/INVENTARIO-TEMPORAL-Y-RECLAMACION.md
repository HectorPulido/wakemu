# Inventario temporal y reclamación de premios

## Bootstrap comprobado

La sección `PROTO_TEMPORARY_INVENTORY` de entidad contiene un short de longitud y bytes del protobuf **lP/ProtoTemporaryInventory**. Tiene campo1 repeated`ProtoItem`/kX. Cada ítem requiere uniqueId1/int64, refId2/int32 y qty3/int32; conserva propiedades opcionales en campos50,51,52,54–58. No usar FightLoot: este último solo describe referencia/cantidad y carece de UID/propiedades.

Se ejecutó un fixture Python con UID12345, ref27083 y cantidad3; `lP.bR` da initialized=true y los getters coinciden. El consumidor cotejado es **biT.zm → fmH.a → lP.bR → fox.y(kX) → fmE.cd**. `fmH` limpia primero el modelo temporal y reconstruye todos los objetos. El fixture prueba el protobuf; todavía no aplica esa reconstrucción sobre una entidad viva ni demuestra el roundtrip de propiedades complejas.

El servidor actual sustituye esta sección por0000 en su adaptador de entidad: no restaura premios pendientes. La implementación debe serializar el conjunto durable de entregas pendientes de ese personaje, usando propiedades ya fijadas al ganar. Validar límite de longitud del contenedor; no envolver un protobuf mayor de32767bytes mediante truncado de short.

## Solicitudes localizadas y encoder ejecutado

| Acción | Opcode | Cuerpo |
| --- | --- | --- |
| Reclamar/mover una cantidad desde temporal | **13993/cqc** | i64 UID objeto, i16 cantidad, byte tipo destino, i64 UID destino, i16 posición |
| Transferencia de lista | **12294/cpX** | i64 personaje origen, i64 personaje destino, i16 cantidad de UIDs, lista i64 |
| Petición de limpiar temporal | **12561/cqb** | vacío |

`cqc` hereda de`cpN`; el origen temporal es implícito y`nJ` solo registra advertencia si se intenta establecer otra fuente. El encoder nativo produjo un frame13993 con21bytes de cuerpo. [Campos, bytes y límites](probe-inventario-temporal-nativo.json). El fixture fija tipo destino0 para probar estructura; la rama de arrastre inspeccionada no llama`dv` y mantiene el default−1. No afirmar que0 sea un tipo válido de bolsa sin cotejarlo. Posición/cantidad usan short, no el byte de otra solicitud de inventario.

`deX` obtiene origen y destino con`biB.Sn` para12294: son **IDs de personaje**, no IDs de cuenta ni contenedor. La vista puede manejar un personaje fuente distinto del destino; el servidor debe acreditar propiedad y permiso de ambos, sin permitir transferencia arbitraria entre cuentas. La UI comprueba capacidad y compatibilidad, pero no sustituye validación del servidor.

12561 se emite dentro de un callback de confirmación, no una petición con lista de UIDs. Falta acreditar el significado completo de esa confirmación antes de habilitarlo: no borrar recompensas durables solo porque se cerró una ventana. Registrar y aplicar una transición autorizada, con posibilidad de rechazo y recuperación coherente.

Ninguno de13993/12294/12561 aparece como handler en el dispatcher actual revisado. No se enviaron estas peticiones a un servidor vivo.

## Actualizaciones12691

`cwO` lee i64 personaje y eventos consecutivos hasta acabar el cuerpo, sin contador global. Eventos0 ADD_ITEM,1 REMOVE_ITEM,2 ITEM_QUANTITY y3 CLEAR. `chH` los aplica al modelo temporal`fmE` mediante`bGe`. ADD_ITEM usa **vj**, serialización nativa de instancia; el bootstrap usa ProtoItem. No copiar automáticamente el cuerpo protobuf del bootstrap dentro del evento ADD_ITEM.

El resumen12755 solo informa del premio;12691 actualiza el temporal. La inserción en una bolsa ordinaria necesita su propio codec. Mantener UID y propiedades entre estas tres representaciones, sin producir otra tirada ni otro objeto al reclamar.

## Transacción propuesta del servidor

Crear entregas identificadas por fight_uuid/participante/ordinal, con UID exclusivo, referencia, cantidad y propiedades. Confirmarlas con XP/kamas antes del resumen. Si no caben en bolsas, persistirlas como temporales; bootstrap y12691 leen esa misma autoridad. No depender de12925 para crear la entrega.

Para13993 validar lease, propietario, cantidad, destino, filtros, capacidad y merge antes de mutar. Reservar o conservar UID según split/merge, actualizar bolsa y saldo temporal en una sola transacción/revisión, y registrar recibo de transferencia. Emitir la inserción de bolsa y reducción temporal después del commit; ante desconexión, el bootstrap conserva el resultado final. No duplicar deltas frente a una mutación optimista sin cotejar el consumidor y la rama UI.

Para12294 fijar por anticipado el conjunto de UIDs y el plan de colocación. Rechazar el conjunto si no puede realizarse íntegro, o definir y comunicar entrega parcial con recibos por ítem; no hacer un loop de commits que pierda cuál fue el último entregado. La UI y su mensaje de falta de espacio requieren cotejo antes de elegir esa política.

## Verificación pendiente

Tipo destino, evento ADD_ITEM/vj completo, propiedades, reducción/merge y mutación optimista; semántica de12561; reconstrucción en GUI al reconectar; compatibilidad Redis y transferencia de lista entre personajes propios. La fuente, bootstrap protobuf y solicitudes ya están identificados. No se aplicó ningún fix.
