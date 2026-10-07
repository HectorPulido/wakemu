# Merkagemas: contratos separados y brecha comprobada

## Inserción, retirada y reorganización son operaciones diferentes

Inspección offline de `bpq`: añadir una gema del inventario utiliza `crH`, retirarla utiliza `crI`; mover entre salas utiliza `crJ`. Se ejecutaron los dos primeros encoders con identidades sintéticas: [frames y hashes](probe-insercion-retirada-nativas.json).

| Operación | Opcode | Cuerpo nativo ejecutado |
| --- | --- | --- |
| Añadir (`crH`) | **12177** | i64 UID del item + byte de sala + **byte final 0**; 10 bytes |
| Retirar (`crI`) | **13090** | i64 identificador de destino + byte de posición destino + byte de sala + boolean; 11 bytes |
| Reorganizar (`crJ`) | **13210** | boolean primaria origen + boolean primaria destino + byte sala origen + byte sala destino; 4 bytes |

El byte final de 12177 está comprobado: `crH.aWH()` reserva diez bytes y escribe nueve; el último queda a cero. No interpretar ese byte como otra selección inventada ni rechazar el frame nativo por exceso de longitud. En 13090 `bpq` resuelve el destino mediante `fkH.at(actor.Xi(),identificador)`; el selector boolean elige primaria/secundaria y se conserva sin cambiarlo. El destino solo se permite si es contenedor propio y posición vacía.

## Código actual y pruebas

No hay ramas 12177/13090 en el dispatcher ni en `protocol_codec.decode_body`; el probe confirma `None` para ambas solicitudes. Existe 13210: exige sesión propia, llama `rearrange_rooms`, guarda layout y publica su configuración. Esa función mueve UID ya instaladas; no toma una unidad del inventario y no implementa inserción nueva.

`rearrange_rooms` conserva controles de salas 0–8, tipos compatibles y protección de primaria: rechaza retirar primaria de sala habilitada hacia hueco vacío, secundaria adjunta o muebles en la sala. Para una sala destino ausente crea configuración vacía y coloca primaria, según la ruta actual. Estas reglas existentes deben cotejarse con el comportamiento nativo antes de reutilizarlas para extracción.

`PYTHONPATH=server python3 -m unittest tests.test_haven_bag_store tests.test_haven_bag`: **17 pruebas aprobadas**. Cubren configuración/persistencia y operaciones existentes; no prueban insertar una gema de inventario mediante 12177 ni retirarla mediante 13090.

## Solución concreta exclusivamente del servidor

Agregar decodificación y handlers separados para 12177 y 13090. Ambos requieren sesión merkasaco del dueño, lease vigente, layout/revisión actuales y validación de identidad en inventario o sala según la operación. 12177 debe resolver el UID declarado en el inventario del actor, comprobar GEM_TYPES y compatibilidad de primaria/secundaria, separar una unidad si hay stack y transferirla a la sala sin duplicar UID. El frame no declara cantidad: la cantidad a transferir necesita cotejo con la lógica nativa de inserción, no debe confiarse a un campo inexistente.

13090 valida sala/selector y contenedor/posición destino; el helper implementado actualiza inventario y layout en una sola transacción y conserva UID, máscaras elementales y ProtoShard. Aún no tiene recibo por nonce/revisión: el protocolo no lleva un identificador de operación y la inserción usa estado final para reconocer repetición.

El orden de split queda propuesto en el helper pero requiere validación cliente: decrementar pila por 12470, insertar UID unitario temporal por 12471, y consumirlo/instalarlo por 12234. No reutilizar 13210 como inserción desde inventario ni permitir visitante por estar en mapa 9. La gema de entrada está protegida; las reglas de sala ocupada siguen sin verificar.

## Implementación de persistencia en progreso

Se añadieron `server/wakfu_server/items/haven_bag_transfer.py` y migración `051_haven_bag_gems.sql`. El helper valida la sesión/personaje, dueño y ubicación del merkasaco, UID/reference del catálogo, tipo de habitación, posición de inventario, y aplica cambios de `inventory_items`, `haven_bag_gems` y `haven_bags.layout` en una sola transacción. Conserva máscaras elementales y ProtoShard al retirar. Si el origen está apilado, reduce una unidad, crea UID separado con slot temporal libre y devuelve en orden 12470, 12471 y 12234; sin slot temporal, falla sin mutar. Un UID ya instalado por el mismo origen/sala se trata como repetición sin una segunda reducción. No cobra kamas; no se encontró costo monetario en los contratos nativos examinados.

`crI`/13090 selecciona primaria/secundaria con el boolean: el consumidor `bpq.a(byte,long,byte,boolean,boolean)` valida `f(room,selector)`; `fvw.nQ(true)` devuelve el objeto primario y `false` el secundario. El cliente resuelve el destino con `fkH.at(actor.Xi(),container_uid)` y aplica 12451 como `(room,container_uid,position,selector,true)`. Por eso el helper preserva el selector y rechaza primaria fija de sala0 o primaria con secundaria instalada.

La suite PostgreSQL cubre decoders strict, split con UID durable único, reintento de inserción, restauración UID/properties, selector secundario, destino inválido/ocupado, estado ajeno y rollback. Los opcodes están conectados al dispatcher de esta fuente, pero aún no se ha validado un intercambio real de cliente; el sistema no está cerrado.

## Límites pendientes

Todavía falta validar el orden de 12470/12471/12234 para split en cliente, probar UI/desconexión/reconnect y completar restricciones de salas con muebles/plantas/visitantes. No hubo transferencia real ni modificación del cliente. Issue abierto.

## Respuestas y orden de aplicación: cotejo adicional

Se inspeccionó `chk` y ejecutaron los parsers nativos `czj/czk/czl`, incluidos cuerpos vacíos que produjeron `BufferUnderflowException`:

| Respuesta | Clase | Cuerpo comprobado |
| --- | --- | --- |
| Inventario → sala **12234** | `czj` | i64 UID + byte sala; 9 bytes |
| Sala → inventario **12451** | `czk` | i64 destino + byte posición destino + byte sala + boolean; 11 bytes |
| Sala → sala **13565** | `czl` | dos boolean primaria + byte origen + byte destino; 4 bytes |

En 12234, `chk` busca primero el item en inventario usando la identidad recibida y después llama a la inserción/sustitución de `bpq` con el flag de aplicación remota. Si el item ya no existe, registra error y no completa esa ruta. **No enviar un delta que elimine previamente ese UID y luego esperar que 12234 lo encuentre.** La división de stack debe conservar un item resoluble para el consumidor, y su UID final necesita prueba de extremo a extremo. Los métodos de `bpq` aplican operaciones locales al recibir la respuesta; aún debe cotejarse si además esperan deltas de inventario para evitar consumo duplicado.

12451 llama a `bpq.a(sala,destino,posicion,selector,true)` y actualiza la sala si el resultado local es `fvx.tkB`. 13565 llama a su reorganización local y actualiza ambas salas. Sus payloads no incluyen un status de éxito ni revisión de oferta. El flag true de `dp()` demuestra parseo, no validez del inventario/permiso.

La ruta actual de reorganización del servidor envía **12187 (`cyX`, configuración tR)** tanto si guarda como si rechaza. `chk` sustituye esa configuración mediante `bpq.a(tR)`; es distinto del resultado incremental 13565. Antes de agregar un ACK incremental debe comprobarse que aplicar resultado y snapshot juntos no mueve dos veces las mismas gemas. Los carriers de error 13008/13959 aparecen en el switch, pero sus casos inspeccionados no muestran una notificación completa: no se ha inventado enum de error.

Estas pruebas cierran layouts de codecs y consumidor local; todavía no prueban una transferencia real del servidor al cliente ni definen carrier nativo de rechazo.

## Cantidad y referencia compartida: seguimiento del consumidor

El consumidor 12234 no es una mera notificación: tanto `bpq.a(byte,fnR,long,true)` como `bpq.b(byte,fnR,long,true)` llaman a **`fnp.b(UID,(short)-1)`**, y después instalan el objeto `fnR` recibido en la sala. Se siguió `fnp` hasta `Rj.b(long,short)`: calcula cantidad + delta; si resulta ≤0 elimina el item del contenedor; en otro caso llama a `Rq.am(delta)` y publica el cambio. Es consumo de **una unidad**, no retirada de toda la pila.

`fvw.m(fnR,true)` guarda el `fnR` recibido como primaria; `fvw.a(boolean,fnR,true)` lo guarda en la ranura seleccionada. Por eso el helper crea una UID unitaria cuando el origen está apilado, publica la reducción del origen y la inserción temporal antes del ACK 12234. Esta secuencia evita compartir la referencia restante del stack, pero falta comprobarla con el cliente conectado.

En la transacción, la unidad apilada queda registrada bajo una UID aparte en la tabla del merkasaco; la fila temporal de inventario existe solo en el cliente entre 12471 y 12234. Las pruebas comprueban la cantidad durable 2 y la UID instalada; la observación de cantidad local y ausencia de doble consumo sigue pendiente de cliente.

Este hallazgo deriva del bytecode inspeccionado, **no de una prueba GUI o transferencia real**. Continúan pendientes la integración del dispatcher, aceptación visual y recuperación ante desconexión durante el orden de paquetes.
