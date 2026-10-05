# Merkagemas: contratos separados y brecha comprobada

## Inserción, retirada y reorganización son operaciones diferentes

Inspección offline de `bpq`: añadir una gema del inventario utiliza `crH`, retirarla utiliza `crI`; mover entre salas utiliza `crJ`. Se ejecutaron los dos primeros encoders con identidades sintéticas: [frames y hashes](probe-insercion-retirada-nativas.json).

| Operación | Opcode | Cuerpo nativo ejecutado |
| --- | --- | --- |
| Añadir (`crH`) | **12177** | i64 UID del item + byte de sala + **byte final 0**; 10 bytes |
| Retirar (`crI`) | **13090** | i64 identificador de destino + byte de posición destino + byte de sala + boolean; 11 bytes |
| Reorganizar (`crJ`) | **13210** | boolean primaria origen + boolean primaria destino + byte sala origen + byte sala destino; 4 bytes |

El byte final de 12177 está comprobado: `crH.aWH()` reserva diez bytes y escribe nueve; el último queda a cero. No interpretar ese byte como otra selección inventada ni rechazar el frame nativo por exceso de longitud. En 13090 `bpq` resuelve el destino mediante `fkH.at(actor.Xi(),identificador)`; falta verificar el significado exacto del selector boolean y si todas las clases de contenedor son legales. No se trata sin evidencia como UID de la gema retirada.

## Código actual y pruebas

No hay ramas 12177/13090 en el dispatcher ni en `protocol_codec.decode_body`; el probe confirma `None` para ambas solicitudes. Existe 13210: exige sesión propia, llama `rearrange_rooms`, guarda layout y publica su configuración. Esa función mueve UID ya instaladas; no toma una unidad del inventario y no implementa inserción nueva.

`rearrange_rooms` conserva controles de salas 0–8, tipos compatibles y protección de primaria: rechaza retirar primaria de sala habilitada hacia hueco vacío, secundaria adjunta o muebles en la sala. Para una sala destino ausente crea configuración vacía y coloca primaria, según la ruta actual. Estas reglas existentes deben cotejarse con el comportamiento nativo antes de reutilizarlas para extracción.

`PYTHONPATH=server python3 -m unittest tests.test_haven_bag_store tests.test_haven_bag`: **17 pruebas aprobadas**. Cubren configuración/persistencia y operaciones existentes; no prueban insertar una gema de inventario mediante 12177 ni retirarla mediante 13090.

## Solución concreta exclusivamente del servidor

Agregar decodificación y handlers separados para 12177 y 13090. Ambos requieren sesión merkasaco del dueño, lease vigente, layout/revisión actuales y validación de identidad en inventario o sala según la operación. 12177 debe resolver el UID declarado en el inventario del actor, comprobar GEM_TYPES y compatibilidad de primaria/secundaria, separar una unidad si hay stack y transferirla a la sala sin duplicar UID. El frame no declara cantidad: la cantidad a transferir necesita cotejo con la lógica nativa de inserción, no debe confiarse a un campo inexistente.

13090 debe validar primero sala/selector y contenedor/posición destino, espacio, capacidades y restricciones de muebles/suelo; luego transferir exactamente la gema instalada. Inventario y layout se confirman juntos con recibo idempotente y revisiones, conservando propiedades del item. No basta llamar a `save_haven_bag()` después de modificar inventario en una transacción independiente.

Resolver respuestas de éxito/error y orden entre delta de inventario y configuración del mapa antes de implementar. No reutilizar 13210 como inserción desde inventario ni permitir visitante por estar en mapa 9. La gema de entrada y salas ocupadas requieren reglas nativas verificadas, sin eliminar contenido para forzar extracción.

## Límites pendientes

Todavía falta ejecutar las operaciones desde UI con Luna, resolver respuestas y boolean de retirada, verificar primaria/secundaria en inserción, cancelación/desconexión y persistencia bilateral inventario/layout. No hubo transferencia real, fix ni modificación del cliente. Issue abierto.

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

Estas pruebas cierran el desconocimiento de layouts de éxito; continúan pendientes inventario real, selector, stack y notificación de rechazo. Solo se añadió documentación y harness privado.

## Cantidad y referencia compartida: seguimiento del consumidor

El consumidor 12234 no es una mera notificación: tanto `bpq.a(byte,fnR,long,true)` como `bpq.b(byte,fnR,long,true)` llaman a **`fnp.b(UID,(short)-1)`**, y después instalan el objeto `fnR` recibido en la sala. Se siguió `fnp` hasta `Rj.b(long,short)`: calcula cantidad + delta; si resulta ≤0 elimina el item del contenedor; en otro caso llama a `Rq.am(delta)` y publica el cambio. Es consumo de **una unidad**, no retirada de toda la pila.

`fvw.m(fnR,true)` guarda ese mismo `fnR` como primaria; `fvw.a(boolean,fnR,true)` lo guarda en primaria/secundaria según la rama, sin clonarlo en esas funciones. Por inspección, un stack >1 puede dejar la misma referencia en inventario y sala después del decremento. No se ha ejecutado el entorno completo para probar sus consecuencias; no se presenta como crash reproducido ni como diagnóstico del bolso Sadida (issue 23).

Esto concreta la implementación propuesta: no emitir un segundo decremento por el consumo ya aplicado mediante 12234. Para stacks debe verificarse la ruta nativa de división y producir una unidad con UID propia resoluble en inventario antes de 12234; mantener el resto bajo su UID y confirmar ambas identidades en la transacción. Si se usa snapshot completo como alternativa, probar la reconstrucción y cantidades sin mezclar arbitrariamente resultado incremental y deltas. Un caso quantity=1 y otro quantity=3 deben demostrar que el resultado conserva una gema instalada y resto 0/2, respectivamente, sin referencias compartidas ni doble consumo.

Este hallazgo deriva del bytecode inspeccionado, **no de una prueba GUI o una mutación de inventario real**. Continúan pendientes los codecs de división, la aplicación completa y recuperación.
