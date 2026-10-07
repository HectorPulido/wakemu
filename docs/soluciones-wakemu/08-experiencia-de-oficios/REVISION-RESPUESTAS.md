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

## XP calculada para crafting de recetas (bytecode local)

El método `boA.a(bol,int)` calcula la XP de una receta. `bol.cmG()` selecciona el oficio, `bol.dAS()` aporta el nivel requerido/de receta y `bol.cmI()` es el coeficiente XP de la receta. La primera llamada `eTD.a((short) nivelOficio, (short) bol.dAS(), definiciónOficio, datosCraftCuenta)` devuelve una base `long`. El bytecode la convierte a `float`, multiplica por `bol.cmI()` en precisión float32 y convierte con `f2l`, que trunca hacia cero; ese entero es la base escalada.

Luego lee el modificador de crafting `eRL.a(eRJ.raI, professionId, context)`, calcula `(100 + modificador) / 100.0f`, multiplica por la base escalada convertida a float32, y vuelve a multiplicar en float32 por `eDv.foo()` (multiplicador global activo). Convierte ese resultado float a double y llama `GS.g(double)` para obtener el `long` final. Por tanto, los productos intermedios usan float32 y la primera conversión flotante a entero trunca; no se debe reemplazar esa etapa por una sola multiplicación decimal/double. El redondeo final depende de `GS.g`; el cotejo posterior de `client/lib/wakfu-client.jar` acredita redondeo hacia arriba de positivos fraccionarios dentro del rango int32; utiliza `d2i` y una suma int32, por lo que no equivale a ceil sin límites para valores extremos.

El nivel de oficio sí tiene curva acreditada independientemente de la recompensa: `eTa.qJ(delta)` suma al total y obtiene nivel mediante `eTD.qM(total)`; al llegar a nivel200 limita el total a `eTD.ee(200)`. La ejecución nativa registrada confirma `ee(L)=75×L²` (nivel1=75, 2=300, 10=7500, 100=750000, 200=3000000). Esto define el nivel acumulado, no la XP que concede cada receta. El catálogo local `protocol/profession-actions.json` contiene 15 IDs de oficio y 443 definiciones de animación/interacción, no una tabla de XP de receta; no acredita recompensa por acción ni fórmula interna de `eTD.a`.

Fuentes: `.runtime/local/review-continuacion-20261004/craft-recipe-boA-boQ.txt` (`boA.a(bol,int)`, descriptor `eTD.a:(SSLeTC;LeDw;)J`) y `profession-xp-eTa.txt` (`eTa.qJ`, `eTD.ee`, `eTD.qM`). Esta especificación cubre el cálculo y la curva demostrados en bytecode, pero deja pendiente cotejar `GS.g`, los operandos internos de `eTD.a` y la política/recompensa de acciones no-receta antes de fijar una fórmula completa de servidor.

## Cotejo completado del cálculo base (6 de octubre)

`eTD.a(L,R,def,rate,account)` usa rate100 en el overload habitual. Si el gate nativo SUBSCRIBER falla y L>=10, devuelve0. Sea d=L-(R+10): d>10 devuelve0; d<0 devuelve Math.round(100*def.cmI()*rate/100) en double; en el intervalo0..10 devuelve Math.round(50*(1+cos((R+10-L)*pi/10))*float32(def.cmI()*rate/100)). XP completa hasta R+10, reducción cosenoidal hasta R+20. `Math.round(double)` redondea al más cercano con empates hacia positivo. El gate de suscripción y los multiplicadores son conceptos separados.

Las definiciones están en `client/contents/bdata/23.jar`, entrada23.bin. El lector independiente cotejado con apv/apC/apE/aKL decodifica15 filas con consumo exacto de15 bytes por fila. La clave del oficio es cmG, usada por eTC.d y eTw; para71 y72, cmI=1.0f. SHA256 JAR: `0dde97177dc5e7f609e5c2adbd920db9a1baa5c3a18b1ae4badac9bdc60d1b43`; bin: `d14c49794bcd972e8e2727313b774e42f64636847cc5e1149bc95a92a7dbf9ce`.

`cWn.eVu()` consulta esta base para decidir el estado visual de cosecha, sin conceder XP. Los siete deltas131 observados para acción2269 no prueban una fórmula universal de cosecha: su coeficiente de acción es1.5 y faltan los modificadores de recompensa aplicables. No sustituir esa evidencia por la fórmula de recetas.

La captura correlacionada contiene tres snapshots13873/CRAFT14 válidos: herbolario72 con0 XP a07:03:11 y07:08:03 UTC, y1697 XP (nivel4) a07:23:03. El replay actual no reemplaza CRAFT14; puede restaurar progreso de la captura en lugar de la autoridad SQL. Corregir tanto el bootstrap como los requisitos y recompensas. El snapshot du conserva mapa de dh, ajustes dA y estado do; dh conserva XP, contadores dk y acciones dJ. No reenviar deltas históricos al reconectar.

## Codec absoluto en implementación

`profession_wire.snapshot` genera13873/CRAFT14 con mapa du/dh: XP absoluta, cuatro contadores y acciones aprendidas. Exige dA y do explícitos del estado propio para conservar configuración adicional. `profession_wire.level` deriva nivel con aritmética entera y rechaza XP fuera de0..3000000. El codec todavía no reemplaza el replay ni lee PostgreSQL; su validación contra el lector nativo está en curso. No acredita recompensa en juego.

## Integración PostgreSQL en verificación

Migración013 reemplaza definitivamente character_professions por account_professions: XP acumulada única, nivel derivado y contadores/acciones nativos; account_craft_state conserva dA/do propios. No quedan consultas runtime al esquema anterior. Los niveles existentes se consolidan por máximo por cuenta/oficio, sin sumar ni mantener un adaptador del esquema anterior.

`profession_store.award` participa en la transacción del producto/acción, valida lease, aplica multiplicador DB, recorta al cap y guarda un recibo por cuenta/operación/oficio. Repetir el recibo no envía otro delta. Los llamadores deben aportar recompensa acreditada y token propio del servidor; la función no inventa XP de cosecha.

El replay reemplaza el carrier CRAFT14 y ensure_learned envía snapshot absoluto después de las notificaciones12675. Codec:6 pruebas Docker OK y parser Java du/eTb verificaron XP150, acciones100/203 y configuración adicional no vacía. La integración SQL y sus fixtures están en verificación aislada; migración013 y código todavía sin recargar en vivo. El gate nativo no sustituye pruebas de entrada y recompensa en cliente.

Gate integrado aprobado:56 pruebas Docker/PostgreSQL aislado (`test_profession_wire test_profession_store test_planting test_resource_collect test_resource_occupations test_planting_runtime test_plant_resource_catalog`). Cubre cuenta compartida, aislamiento, XP parcial/dA/do al reabrir, recibos sin delta duplicado, rollback con efecto de acción, lease obsoleto, cap, multiplicador inválido y migración de varios personajes por máximo. Esta evidencia no acredita cosecha en cliente ni una fórmula oficial de recompensa.

## Recarga verificada

Imagen world `335c7ce4ef2abbbac70462fde08519299304967c72efd941f702be44709d17b6`, recreada con `docker compose up -d --no-deps world` tras gate56 y comprobación SQL de cero combates en colocación/activos. Backup previo1.215.613 bytes en `.runtime/backups/pre-account-professions-XXXXXX.dump`. Docker healthy; schema_migrations001..013, tabla character_professions ausente y12 filas account_professions. Generación de carrier propio13873 de82 bytes para cuenta de auditoría comprobada. Recarga aplica dos migraciones012/013; ninguna lógica de hechizos fue modificada. Validación visual de cuenta nueva encargada a Luna low; resultado todavía pendiente.

Prueba visual delegada a Luna low con cuenta nueva5: los logs acreditan token y Authentication result0. No se pudo observar GUI: screenshot falló `could not create image from display` y System Events no enumeró ventanas. No se creó personaje ni se concedió XP en esa cuenta; entrada al mundo y barra de oficio no verificadas. El aviso userInfo.missing no bloqueó autenticación, según la secuencia posterior. El cliente/bridge propios de la prueba fueron cerrados; ningún otro cliente fue terminado.

## XP efectiva de plantación — política local explícita

La respuesta del usuario en `04-probabilidad-de-plantacion/FALTANTES.md` autoriza inventar una fórmula local: plantar entrega poca XP, cosechar más y recetas según casillas, todo configurable en PostgreSQL. No hace falta esperar una fórmula oficial para esta política. La migración015 introduce `profession_action_rewards` versión1: `planting_xp=10`, `harvest_xp=50`, `recipe_slot_xp=100`, valores enteros de0 a3.000.000. El multiplicador global ya existente se aplica después con división entera por10.000 y cap nativo3.000.000. Recetas admiten1–16 casillas en el lector de política; su ejecución está conectada en fuente a crafting.complete: casillas distintas de ingredientes × recipe_slot_xp × creaciones del lote, con recibo y consumo/producto/XP atómicos. Pendiente desplegar y aceptar visualmente.

`planting.complete()` acredita la XP de plantación dentro de la misma transacción que consume la semilla, crea el recurso y registra el recibo. Solo ocurre tras finalizar exitosamente; cancelar, rechazar, fallar o repetir no concede XP. La clave de crédito usa dominio `planting:` y SHA256 del token para conservar el límite de128 caracteres y no colisionar con otras acciones. Se añade12916 únicamente si el crédito es positivo; a nivel máximo no hay delta. Política inválida o profesión ausente revierte toda la operación. Pruebas de integración y despliegue pendientes; esto no declara resuelta la XP de cosechas ni recetas.

### Validación y carga de014–015

Gate final: **41 pruebas OK** (`test_planting`, `test_planting_runtime`, `test_profession_store`, `test_resource_occupations`, `test_postgres_migrations`) en Docker/PostgreSQL aislado. Comprueba crédito real10XP/12916, duplicado sin segundo crédito, cancelación sin XP, rollback completo por configuración inválida, multiplicador con cap, token de128 caracteres y rechazo antes de iniciar sin oficio incluso con override. El lector de política de recetas está probado; no demuestra recetas ejecutadas.

Imagen `c5da66d48c4b6994f149fe2b8c99be88f9a5f4d8291b2810d3514d40abfedb69` recargada tras comprobar cero combates y reservas activos. Respaldo privado previo `.runtime/backups/pre-profession-xp-XaEFLf` de1.226.143 bytes. Arranque aplica dos migraciones; PostgreSQL real enumera1–15, conserva política10/50/100 y devuelve10 al lector de plantación. Docker healthy y `/health` confirma PostgreSQL. No se modificaron hechizos ni lógica de combate. Aceptación visual de la XP de plantación pendiente; cosecha y recetas siguen sin conectar al crédito.
