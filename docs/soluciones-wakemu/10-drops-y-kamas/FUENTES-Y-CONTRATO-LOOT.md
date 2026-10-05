# Fuente nativa de botín y contrato del resumen

## Fuente existente que se había omitido

`server/protocol/monster-encyclopedia.json.gz` ya contiene **2874 monstruos,16138 filas de drops de combate y2204 tablas externas**. Se obtiene de los datos instalados mediante `sniffer/java/ExportMonsterEncyclopedia.java` y `server/tools/export-monster-encyclopedia.py`. El exportador carga localmente `aMb/aMf` y`fFc`; no necesita conexión con servidores oficiales. No se regeneró el catálogo ni se modificó el cliente durante esta revisión. Además se ejecutó un probe offline que volvió a cargar los datos binarios actuales con`apw/aMb` y confirmó directamente las cuatro filas de Esquirlas de Kralaman, independientes del JSON exportado.

Cada monstruo tiene`ref`, `family_id` y`combat_drops`. Cada fila conserva referencia, probabilidad, número de tiradas, cantidades mínima/máxima, bandera de tabla externa, criterios simples/complejos y campos nativos todavía sin nombre semántico. **Los drops se relacionan por referencia de monstruo**, no basta asignar la misma lista a toda su familia. Los datos permiten una política del servidor apoyada en el catálogo real.

La ruta visual es`bbo.a(aMb,short) → ble/fqH → bld → brq/brB`. `aMf.cmY` es probabilidad en0..1; la UI la muestra multiplicada por100. `brB.dIo` interpreta `roll_count<=0` como **un intento para cada jugador**; un valor positivo muestra una cantidad de intentos. No cambiar−1 por cero intentos.

## Cotejo de la captura del usuario

Kralaman es **ref2709**, familia702. Esquirlas son **item27083**, máximo de stack9999. El catálogo contiene probabilidad0.05, `roll_count=-1`, cantidad3..3 y condición`MIN_STASIS_LEVEL=3`. Esto concuerda con el tooltip de5 %, intento por jugador y Stasis mínimo3. La captura también muestra el selector Stasis2: visualizar el objeto no acredita que sea elegible en esa dificultad. A Stasis2 el servidor debe rechazar esa fila; a3 cumple esta condición.

Hay **cuatro filas idénticas** de Esquirlas en los datos crudos. La UI `brq.a(Map,bld)` agrupa por hash de referencia, probabilidad redondeada, criterios, flag complejo y tiradas: oculta duplicados sin sumar probabilidades. Eso explica una sola entrada visual. No acredita cuatro tiradas independientes ni que el servidor deba deduplicar por referencia; hay que resolver el origen y semántica de cada fila antes de generar recompensas. Conservar índice/identidad de fila en el catálogo derivado y recibo.

## Condiciones y tablas externas

Hay686 filas con criterio complejo. Las condiciones simples observadas incluyen `NOT_IN_DUNGEON`, `MIN_STASIS_LEVEL`, `ONLY_IN_DUNGEON`, `ONLY_WHEN_DOWNSCALED`, `NOT_IN_INFINITE_WAVES`, `CAN_BE_LOOTED_IN_STELE`, `MIN_SCORE`. Obtener esos valores del contexto autoritativo de combate/mazmorra/brecha; no del tooltip ni del cliente. Un criterio no implementado debe registrarse como tal y evitar premios indebidos, sin perder silenciosamente una fila que sí es válida.

`fFc/fFe` aporta tablas externas y expresiones como`IsNeoServer()`. `brq.d` resuelve una tabla, suma pesos no negativos, normaliza por esa suma y recorre referencias anidadas; una probabilidad negativa se trata como1 en esa ruta visual. Es evidencia de presentación de probabilidades, no demostración completa de cómo tira el servidor. Validar referencias, ciclos y contexto antes de habilitar cada tabla. Las16138 filas de combate observadas no tienen`is_loot_table=true`; no atribuir las2204 tablas externas a enemigos sin acreditar su enlace.

`brq.Y` calcula el porcentaje personal combinando prospección, dificultad, otros factores y cap1. La pantalla no requiere inventar tasas en el servidor. Para la política pedida, la fórmula Dofus está extraída en [FORMULAS-DOFUS.md](../09-experiencia-de-combate/FORMULAS-DOFUS.md); distinguirla de la fórmula visual Wakfu si se decide conservar su multiplicación de factores. No sumar/multiplicar Stasis dos veces.

## Resumen12755: contrato y fixture ejecutado

Se ejecutaron descriptores y parsers del cliente instalado:

| Mensaje | Campo | Tipo |
| --- | --- | --- |
| `FightPlayer`/je | 7 `loots` | repeated `FightLoot`/iW |
| `FightLoot`/iW | 1 `itemRefId` | required int32 |
| `FightLoot`/iW | 2 `quantity` | required int32 |
| `FightLoot`/iW | 3 `isPurseLoot` | optional bool |
| `FightLoot`/iW | 4 `isPvpLoot` | optional bool |
| `FightReport`/ji | 9 `stasisLevel` | optional int32 |

Fixture Python con personaje sintético12345/cuenta67890 y Esquirlas×3, flagsfalse/false: `je.bj` da initialized=true; getters devuelven27083/3. El fixture completo con prefijo de combate de12bytes y protobuf se procesa por **cvJ.dp**, opcode12755, fight7, Stasis3, initialized=true y mismo botín. [Resultados y hashes](probe-fuentes-loot-y-resumen.json). No se inyectó ese resumen en una sesión ni se concedieron objetos.

Consumidor cotejado: `cju → aUI.cby → daW → bvS → bvR.dNt`. La lambda usa`je.Sq`; cada entrada se convierte en`fnP(iW)`, que resuelve plantilla por`itemRefId`, convierte cantidad a **short** y conserva los flags. El resumen no transporta UID ni propiedades de la instancia: esas pertenecen a la entrega de inventario. Validar/agrupar cantidades como máximo32767 por entrada antes del cast, aunque protobuf admita int32. No confundir aparecer en el resumen con estar persistido en una bolsa.

`combat_results._player` actual no emite campo7. La implementación debe añadirlo desde el recibo final comprometido, conservando jugadores/equipos y campos existentes; enviar por el mismo12755. Para cada unidad/stack usar los codecs de inserción de inventario ya existentes y la autoridad transaccional adecuada. El resumen se deriva de ese recibo, jamás vuelve a tirar botín.

## Pendientes reales

Resolver el alcance de rollMax y filas repetidas, condiciones complejas y enlaces de tablas, integración del servicio y política de inventario lleno. Los nombres rollMax y prospección mínima ya fueron acreditados; véase la ampliación siguiente. Después probar cantidades/flags y resumen visible con dos participantes, entrega persistente, crash y reconexión. **La fuente de loot y el contrato nativo del resumen ya están localizados y probados de forma sintética.** No se aplicó ningún fix ni se modificó el cliente.


## Campos adicionales resueltos y límite del consumidor

El recipe de`fqG.toString` conserva nombres originales de campos: `csE` corresponde a **m_rollMax** y `csF/giP` a **m_minProspection**. En las filas de combate actuales, rollMax es−1 en14795 filas y1 en1343; prospección mínima es0 en las16138. El constructor nativo copia csE a byte mediante`fqH.gF`, pero el exportador conserva el short original. Para el catálogo observado no hay overflow en esa conversión.

Las filas de Esquirlas tienen rollMax1 además de intentos por jugador y cantidad3. No confundir el máximo de roll con la cantidad de objetos ni omitirlo al copiar la fórmula Dofus. La búsqueda de referencias al getter en el jar encontró construcción/serialización y representación, sin un ejecutor autoritativo de tiradas que acredite si el cap aplica por fila, enemigo o combate. La UI agrupa filas y descarta cantidad/cap al reconstruir la entrada visual; no puede certificar esa semántica del servidor. La propuesta debe conservar filas y cap, y probar una política explícita de reparto antes de habilitarla.

## Inventario temporal: ruta nativa localizada

Existe un inventario temporal nativo, no hace falta inventar una ventana. `cwO`/12691 lee i64 personaje y una secuencia de eventos tipados hasta el final del cuerpo. `fmX` identifica0=ADD_ITEM,1=REMOVE_ITEM,2=ITEM_QUANTITY,3=CLEAR. `chH` busca el personaje, toma su inventario temporal`fmE` mediante`fmw.sEU`, aplica eventos a`bGe` y actualiza`dco.feY`. ADD_ITEM utiliza`fmR` y la serialización de ítem`vj`; no usa FightLoot, porque necesita instancia/UID y propiedades.

El bootstrap conserva una sección`PROTO_TEMPORARY_INVENTORY`, cuyo contenedor`rQ` lee un short de longitud y sus bytes; el default actual del servidor es0000. Por eso una entrega pendiente debe reaparecer también al cargar/reconectar, además de un delta12691. Leer su contenido protobuf y petición de reclamación sigue en investigación; no enviar bytes del resumen12755 como contenido temporal.

Una búsqueda restringida a wakfu.com sobre inventario lleno/temporal no devolvió resultados. Eso no elimina la evidencia del cliente: el código acredita el mecanismo y su actualización, aunque todavía no acredita que todas las recompensas oficiales con bolsas llenas usen esa política ni cuánto tiempo se conservan.
