# E15 — Modelo nativo y propuesta de persistencia

## Contrato acreditado

Se inspeccionaron los descriptores protobuf instalados y se probó `jU.bt → fgL.fK` con un gremio sintético 456, nivel 1 y nombre «Audit Guild». El consumidor conserva identidad, nivel y nombre. No equivale a crear un gremio funcional: el fixture no contiene miembros ni rangos.

| Modelo | Campos nativos |
| --- | --- |
| Gremio | `guildId` 1, `level` 2, `blazon` 3, `name` 5, `description` 6, `message` 7, puntos actuales 8 y totales 9, límite semanal 10, límite de puntos ganados 11, última semana de ganancia 12; listas de rangos 13, miembros 14, bonus 15. |
| Rango | ID i64, nombre, máscara de autorizaciones i64, posición i32. |
| Miembro | ID i64, `ownerId` i64, puntos i32, rango i64, XP i64, conectado bool, smiley/sexo bytes, raza/nación i32, nombre, fecha de guardado i64, idiomas y comunidad bytes. |
| Bonus | ID i32, fecha de activación i64, fecha de compra i64. |

Los escalares descritos están marcados **required**. No confundir miembro con cuenta hasta resolver `ownerId`, ni asignar unidades de fechas sin cotejarlas. [Evidencia y números completos](probe-modelo-gremio-protobuf.json).

## Persistencia propuesta exclusivamente del servidor

Separar tablas `guilds`, `guild_ranks`, `guild_members` y `guild_bonuses`, con claves estables y referencias hacia gremio/rango. Guardar máscara completa de 64 bits; ningún valor enviado por la interfaz concede permisos por sí mismo. Nombre visible y clave de unicidad normalizada son columnas diferentes; la regla de normalización aún requiere cotejo.

Crear gremio, rangos iniciales, membresía del fundador y débito de ítem/kamas en una transacción, junto con un recibo de operación para evitar doble cobro al reintentar. Un rango de otro gremio no puede asignarse a un miembro. Invitaciones necesitan identidad del emisor/receptor, vencimiento y estado consumido; aceptación debe volver a comprobar cupo y permisos bajo transacción.

Tratar conexión como presencia derivada de sesiones, sin restaurar `isConnected=true` desde una fila histórica después de reiniciar. Persistir puntos y fechas solo mediante operaciones autorizadas e idempotentes. La elección de líder, cupo, derechos concretos y reglas de bonus siguen pendientes de cotejo; no se inventan a partir de nombres de campos.

## Restauración e interfaz

`dbG` solo abre gestión cuando `biB.dtC()` indica gremio y envía `cps` **15877**, cuerpo vacío. `bxk` obtiene el modelo privado `fhV` desde `bkY.dvE`; `bkY.a(long,byte[])` carga protobuf mediante `fgL.a`. Identidad remota `rV` y aviso de creación 1000 son contratos separados. Falta localizar el carrier que entrega el modelo privado y sus deltas, probar permisos y comprobar reconexión/reinicio con dos personajes.

No se creó esquema ni se implementaron handlers.

## Sección local: ruta de restauración comprobada

`GUILD_LOCAL_INFO` es ordinal **31** de `eHe`, clase `qH`: longitud u16 del `ProtoGuildModel`, sus bytes y float32 `moderationBonusLearningFactor`. La sección vacía ocupa 6 bytes. Se probó serialización y decodificación nativas de un protobuf de 34 bytes: sección de 40 bytes, ID y factor conservados, sin bytes sobrantes. El factor 0,25 es sintético, no una tasa oficial.

El observer `biK` registra `qH.DM`; al actualizar llama a `bkY.a(character_id,VD)`, carga el modelo mediante `fgL`, aplica el factor y actualiza el personaje. Esto identifica la restauración local, pero **31 no es un opcode de transporte**. Los layouts actuales de fixture no incluyen esta sección: falta cotejar el formato que la transporta y sus deltas antes de proponer un splice o paquete final. [Prueba](probe-seccion-local-gremio.json).

## Actualizaciones de miembros, rangos y bonus

Se acreditó **15367/cDh**: ID de gremio i64, cantidad i32 y, para cada delta, longitud de payload i32, tipo byte y payload. Se probó el consumidor con un delta de retirada de miembro: gremio 456, miembro sintético 999, 25 bytes totales. No hubo expulsión real.

Tipos nativos: 0 añadir miembro; 1 retirar; 2 modificar; 3/4/5 añadir/retirar/modificar bonus; 6/7/8 añadir/retirar/modificar rango; 9 mover rango; 10 puntos; 11 nivel; 12 descripción; 13 mensaje; 14 nombre; 15 emblema. Los cuerpos varían por tipo; el protobuf de creación no sustituye el envelope de deltas.

`clo` aplica estos deltas solo a modelos `fhV` **ya cargados** cuyo ID coincide. Para reconexión hay que enviar estado completo antes de deltas; una notificación 1000 y deltas a un modelo ausente no restauran el gremio. El envelope no muestra revisión/contador de secuencia: mantener versiones/orden en el servidor y outbox, sin insertar bytes que el cliente no consume. Emitir deltas tras commit; al recuperar/reconectar restaurar snapshot coherente y evitar replay antiguo. [Prueba](probe-transporte-deltas.json).

## Rangos y permisos: contratos cotejados

Se ejecutó el enum `fgI`: 27 permisos, bits 1–27, incluyendo invitar/expulsar/cambiar rango/editar rango, retirada de ítems y dinero de cofre, descripción/mensaje, compra de bonus, merkamundo y compartimentos de cofres. Cada máscara conserva su permiso al decodificarla. No confundir bits con ordinales: `ADD_MEMBER` ocupa bit 1 (máscara 2). El campo protobuf es i64 aunque los permisos presentes usen bits bajos.

Las solicitudes de rangos usan **categoría 6**, diferente de creación de gremio categoría 3: **15194** crea rango (longitud byte + nombre UTF-8 + máscara i64), **14088** retira rango (ID i64), **14815** modifica (ID i64 + máscara i64 + longitud byte + nombre). Se ejecutaron encoders nativos con fixtures. La UI limita a 15 rangos y nombre a 16 unidades de `String.length`; el servidor debe comprobar también longitud en bytes y jerarquía. No basta con permitir un botón: revalidar rango del actor y alcance sobre el rango objetivo al ejecutar la transacción.

La auditoría integral de E15 debe incluir cofres, tesorería y merkamundo porque los permisos instalados los contemplan. Su presencia no acredita que estén implementados ni determina todas sus reglas. Evidencia: `probe-permisos-y-rangos.json`.

## Jerarquía de rangos: comprobación nativa

Se ejecutaron **1.080 casos** con los 27 permisos, cuatro posiciones de actor, cinco posiciones objetivo y presencia/ausencia del bit. `REMOVE_MEMBER`, `CHANGE_MEMBER_RANK` y `EDIT_RANK` requieren posición del actor menor que la del objetivo, salvo posición 0. **La posición 0 no evita comprobar el bit del permiso**. Los demás permisos no aplican esa comparación en esta función. `target=-1` omite la comparación de posición en el cliente; no aceptar ese sentinel como permiso para saltar validación autoritativa.

El servidor debe calcular ambas posiciones desde rangos persistidos del mismo gremio, revalidarlas bajo transacción y no confiar en valores enviados por la interfaz. Falta cotejar restricciones de asignación de rango, transferencia del fundador/líder y disolución; esta función no las demuestra. [Prueba](probe-hierarchie-rangs.json).


## Reordenación y retirada de rangos

Se ejecutó `cCc`: solicitud **15429**, categoría **6**, cuerpo de **10 bytes** (ID de rango i64 + posición i16 con signo). Se conservaron seis posiciones, incluida −1 y 32767. **El encoder no valida su legalidad**: no aceptar todo el rango i16 como posiciones funcionales. `bxk.i` envía la solicitud sin comprobación de jerarquía en ese método; revisar permisos en el servidor incluso si otra parte de la UI oculta el control.

El delta `MOVE_RANK` usa `fhK`, serializa un rango mediante `fgL.l`, decodifica mediante `fgL.fL` y aplica ID/posición por `fgz.i → fgF.i`. No reutilizar el cuerpo de solicitud como cuerpo del delta. `fgz.i` comprueba que el rango exista.

El consumidor `fgz.rZ` de retirada comprueba existencia, prohíbe retirar rango superior e inferior y rechaza rangos asignados a miembros. La solución debe revalidar esas condiciones con filas persistidas bajo transacción: evitar que una aceptación/asignación concurrente deje una referencia huérfana. No borrar primero y trasladar miembros después; cualquier reasignación requiere una operación explícita autorizada y atómica. Reordenar debe mantener un orden coherente y emitir deltas de todos los rangos afectados tras commit. Se ejecutó `fgF.i` con cuatro rangos en posiciones 0, 1, 2 y 3: mover el último a 1 deja **0, 1, 2, 1**. El consumidor cambia solo el rango indicado y no desplaza los demás. Si el servidor mantiene posiciones únicas, debe calcular el desplazamiento de los afectados y enviar cada delta; un único delta no basta. Esto no prueba que el servidor oficial prohíba empates: la unicidad y los límites de posiciones requieren cotejo adicional.

[Prueba y límites](probe-reordenacion-y-borrado-rangos.json). No se creó ni modificó un gremio real.


## Cupo y duplicados de miembros

Se ejecutó `fgF + fgz` con miembros sintéticos `fia` mediante proxies: a 199 miembros `isFull=false`, a 200 y 201 `true`; añadir de nuevo el ID 201 conserva el contador. `fgF.isFull` compara **cantidad de miembros ≥ 200 + skP**. Un incremento sintético de 5 mediante `Uq` deja 201 miembros por debajo del cupo. El origen de ese incremento todavía requiere cotejo: no se atribuye a nivel, compra o bonus concreto.

`fgz.f` evita añadir un ID ya presente, pero **no rechaza el miembro 201 por cupo**. Es un consumidor de estado, no autoridad de invitaciones. El servidor debe calcular el cupo desde configuración/bonus acreditados y comprobarlo atómicamente al aceptar, junto con membresía previa y validez de invitación. Dos aceptaciones concurrentes para la última plaza no pueden autorizarse a partir del mismo contador anterior. No confundir cantidad de registros `fia` con cuentas únicas hasta resolver `ownerId`.

[Probe ejecutado y límites](probe-cupo-miembros.json). No se probó invitación real ni persistencia SQL de miembros.
