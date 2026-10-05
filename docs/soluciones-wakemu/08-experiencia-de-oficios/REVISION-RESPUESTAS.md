# Oficios: curva y delta cotejados

## Estado del servidor

`profession_store` persiste solo profesión/nivel0–200. Aprender12675 no concede XP; plantación consulta requisito, pero no recompensa oficio. El esquema carece de XP acumulada y recibo de recompensa. Las respuestas del usuario remiten a04: multiplicador configurable, éxito con XP, fallo/cancelación sin XP.

## Contrato nativo ejecutado

**12916/cux** es i32 profesión + i64 **delta XP**,12bytes. `chh` llama `eTo.D`; `eTe.D`→`eTa.qJ` suma al total anterior y notifica. Se ejecutaron dos deltas75: total75 y150, ambos nivel1. Reenviar el mismo paquete duplica XP visual: no usarlo como snapshot absoluto ni como respuesta idempotente de reconexión.

`eTD.ee(L)` calcula **75×L²**; `qM(total)` usa floor(sqrt(total/75)). Umbrales ejecutados: nivel1=75,2=300,10=7500,100=750000,200=3000000. `eTa.qJ` limita el acumulado a3000000 al alcanzar200. [Prueba y límites](probe-curva-y-delta-nativos.json).

## Multiplicador sin modificar cliente

La curva visual está calculada en el cliente. Cambiar únicamente umbrales del servidor produce desacuerdo de nivel/barra. Implementar el multiplicador solicitado en **XP otorgada**, conservando unidades nativas y curva75×L², y etiquetar esta adaptación explícitamente. Mantener multiplicador DB como entero en puntos básicos, default10000 (1×), rango propuesto0–1000000 (0–100×), XP final floor(base×mult/10000), cap acumulado3000000. Estos límites son propuesta del emulador, no valores oficiales ni implementación aplicada.

Persistir XP acumulada, derivar nivel y migrar niveles antiguos con XP inicial75×nivel² para preservar su nivel. Esa migración pierde progreso parcial desconocido, que no existe en el esquema actual; probar copia antes de activar. Crear recibo único por operación/oficio y confirmar XP/producto/consumo juntos. Emitir12916 con **incremento realmente aplicado**, recortado al cap. En reconexión enviar carrier absoluto verificado; no replay de deltas ya consumidos.

Para crafting base configurable según número de ingredientes/casillas; para plantación base menor que recolección, con tabla DB versionada por acción/recurso. No confundir número de casillas distintas con cantidad total de ingredientes. Resolver primero las fuentes de esa acción (issue30).

## Límites pendientes

No hubo recompensa en vivo; falta cotejar bootstrap absoluto de XP, desbloqueos/13186 y notificaciones de niveles múltiples, además de recuperación tras commit sin ACK. La aceptación del parser no prueba esos recorridos.

## Bootstrap completo frente a secureCraft

Se ejecutó la serialización/restauración nativa con total150 XP: `eTa.fJj()`→**dh**→`eTa.a(dh,null)` conserva **150**; `eTa.fJl()`→**gg**→`eTa.d(gg)` restaura **75**, el umbral del nivel1. gg contiene nivel y acciones; no conserva avance parcial. El consumidor `eTe.a(du,boolean)` borra el mapa de oficios y carga dh; `eTe.a(gk,boolean)` carga gg.

**12818/cuy** transporta i64 identidad + i32 tamaño + gk para secureCraft; no usarlo como snapshot de XP completa. La solución debe adaptar el carrier propio basado en **du/dh**, conservando campos de acciones y demás estado. No enviar delta150 después de cargar nivel1 mediante gg, pues ya hay75 y resultaría225; tampoco reenviar deltas históricos tras bootstrap completo.

El primer harness falló por usar un nombre de método inexistente; una segunda introspección de descriptor falló por getters protobuf ofuscados. La prueba final utilizó los getters/serializadores nativos directamente y pasó. [Resultados y alcance](probe-bootstrap-completo-vs-secure.json). Falta identificar/revalidar el contenedor exterior de du en el bootstrap real y ejecutar reconexión con XP parcial; no se da por resuelto el flujo completo.

## Autoridad nativa de cuenta, no de personaje

El consumidor `chh.dtx()` obtiene **ID cuenta** por `aTJ.xl()` y consulta `bcq.iJ(accountId)`. bcq recupera `bdB.a(eDS.oUy)` y lo identifica como **CraftAccountData**; `eDS.oUy` es **CRAFT**, ordinal14. `eTb` conserva un eTo completo: su deserializador lee **i32 longitud + du**, sin ID de personaje dentro de ese bloque, y su serializador devuelve el mismo formato.

Esto cambia el diseño propuesto: el esquema actual `character_professions(character_id,profession_id,level)` está organizado por personaje, mientras el modelo propio nativo está organizado por **cuenta**. Antes de implementar XP, usar autoridad de cuenta/oficio y obtener ownership por sesión de la cuenta; el personaje conserva contexto de la acción y recibo, no debe ser la clave única del progreso compartido. Ensayar dos personajes de la misma cuenta con IDs diferentes y otro de otra cuenta, conservando avance entre selecciones y evitando compartirlo entre cuentas.

La migración de varias filas antiguas por oficio/cuenta requiere regla explícita del emulador: **propuesta preservar el máximo nivel existente**, inicializar su XP a75×nivel² y registrar filas de origen; no sumar niveles o umbrales de todos los personajes. No se ejecutó migración.

La envoltura exterior del estado CRAFT todavía necesita cotejo del mensaje de accountData y de su índice serializado: ordinal14 no acredita por sí solo un opcode ni tag protobuf. El bloque i32+du sí está comprobado en bytecode eTb. No tratarlo como sección de la entidad personaje. [Hallazgo estructurado](probe-autoridad-cuenta-oficios.json).

## Envoltura exterior y restauración ejecutadas

Se resolvió el carrier pendiente: **13873/cwf** entrega bytes a `cib`→`bdB.ci`→`eDP.d(accountId,bytes)`. eDP lee i32 número de secciones e i32 ordinal por sección y llama al deserializador eDN. Para CRAFT el cuerpo es **i32 count=1, i32 state=14, i32 tamaño, du**. El ordinal14 sí queda acreditado en esa posición por el consumidor, no inferido de una coincidencia.

Se construyó du sintético con oficio40/XP150, se pasó por la envoltura y **el registro nativo eDP de cuenta987654321 restauró total150**. Esta prueba ejecuta el deserializador de estado completo, no solo dh. No usó la interfaz ni paquetes en vivo. [Resultados](probe-carrier-craft-cuenta.json).

`local_game_server.replay` ya sustituye secciones13873 de transporte12 y tutorial13, pero no tiene sustitución propia CRAFT14. Integrar aquí el bloque autoritativo de oficios de cuenta y en refresh pertinentes, preservando otras secciones. No asumir un formato por personaje ni borrar el accountData completo. Falta decoder/encoder Python verificado de du/dh y prueba de reconexión en cliente; el layout exterior y la conservación de XP parcial ya están comprobados.
