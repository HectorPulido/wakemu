# Revisión de código y contrato — mesas de oficio

## Actualización de sincronización — 7 de octubre de 2026

El patrón reportado (mesas/Zaaps que reaparecen al recargar el cliente) coincide con un hueco de publicación: `local_game_server.py` respondía con el snapshot completo solo al recibir `14689`, pero los cambios de mapa con caché no siempre generan esa solicitud. El request nativo `cDt/14689` usa envoltorio de categoría6 con cuerpo de cero bytes; no especifica chunks ni radio. El consumidor de `13984` (`cEX`) busca cada ID en el registro de interactivos ya cargados y omite los IDs que no existen, por lo que `13984` actualiza estado y no crea objetos.

La fuente actual arma un snapshot de mapa completo tras cada `join_world`, mantiene el envío pendiente si el personaje aún está en combate, valida `account_id/generation` antes de publicar y hace hasta tres reintentos desde `idle()` con intervalo750ms. Un request14689 lo adelanta; una acción validada de movimiento/interacción también lo adelanta y cancela los reintentos. El patrón evita depender de una inferencia de radio de chunks y cubre objetos junto a los límites de chunk. Los mapas instalados producen cuerpos de hasta60,078 bytes; Astrub1134 usa21,155 bytes.

La corrección está en fuente, sin imagen nueva, despliegue o confirmación visual. Gate Docker aislado: **114 pruebas aprobadas**, incluidas `test_world_static` 3/3 y `test_static_map_sync_dispatch` 9/9, más despacho crafting, estaciones, inventario, transportes y recompensas de combate. La [prueba manual conjunta](PRUEBA-GENERAL.md) queda pendiente de imagen candidata.

## Presencia y ruta actual

El catálogo actual contiene **330 CraftTable en 33 mapas**, incluidas 26 mesas en Astrub 1134. El [probe ejecutado](probe-presencia-ruta-mesas.json) registra todas las de ese mapa y hashes de las fuentes. Ejemplo próximo a la posición reportada: 31515 en (-20,10,-4); no todas están en la altura del personaje. La presencia en el catálogo no prueba que el entorno nativo las haya registrado o renderizado.

`world_static.snapshots()` incluye estas filas en 13984; `local_game_server.py` las publica al recibir 14689, solamente en instancia 0. Ese paquete actualiza objetos existentes: no crea una entidad ausente del entorno. El clasificador de 12870 devuelve `unsupported` para una solicitud sintética ACTIVATE a cada mesa de Astrub; el dispatcher registra y continúa. **Esta prueba no demuestra que el botón nativo de crafting envíe 12870.** Importar el módulo correctamente requiere `from wakfu_server import world_static`, según el paquete actual; un intento con `wakfu_server.maps.world_static` falló por resolución relativa y fue corregido únicamente en el harness.

## Interfaz nativa: corrección del plan anterior

Inspección offline de `bAq`, `bAp`, `cWp` y `dag`: la factoría CraftTable crea `bAp`; `dSG()` interpreta el parámetro textual como ID de definición `bFv`, consultada mediante `flz`/`flT.szn`. Por tanto, el texto `81` observado es una clave de definición, **no acredita que sea oficio 81**. `dSw()` necesita esa definición y el oficio registrado en `fyB` para ofrecer acciones.

`cWp.run()` comprueba acceso y acercamiento; `eVB()` llama `dag.a(bFA,boolean)`. `dag` abre localmente `craftTableDialog` o `craftTableFreeDialog`. No procede inventar un ACK del servidor para abrir esa ventana. Falta probar la visibilidad y apertura con el cliente real, incluida la inicialización de definición/oficio y estado de la mesa.

## Ejecución de receta

El encoder nativo `com` emite **12231**, categoría 3, cuerpo de 16 bytes: i64 mesa, i32 receta, i32 cantidad. `coo` emite **13515**, cuerpo de 24 bytes: i64 mesa, i32 receta, i64 valor obtenido de `boQ.dCv()`, i32 cantidad. El significado de ese i64 y la modalidad `boA.dBh()` siguen pendientes; no se ha supuesto que sean una receta ordinaria.

El [probe nativo](probe-solicitudes-crafting.json) ejecutó ambos encoders con mesa 31515, receta sintética 123, cantidad 2 y valor adicional 67890. **No son recetas oficiales válidas ni una producción real.** El codec Python contempla 12231; el dispatcher actual no contiene handlers 12231/13515. Debe seguirse también la vía de improvisación `conn`, cancelación y resultados antes de especificar respuestas.

## Solución concreta exclusivamente del servidor

Conservar las entidades nativas y distinguir diagnóstico de visibilidad de ejecución. Validar la mesa contra mapa, instancia, posición, definición y oficio; incorporar la receta desde su catálogo nativo, con ingredientes, producto, nivel y duración comprobados. Implementar el handler 12231 y separar la modalidad 13515 una vez resuelta su semántica. Una sola transacción debe consumir ingredientes, crear producto y conceder XP; revisión y recibo evitan repetir producción tras retry o reconexión. Resolver primero los contratos de respuesta y actualización de inventario/oficio, sin usar 12870 como sustituto arbitrario de 12231.

## Pruebas y límites

`PYTHONPATH=server python3 -m unittest tests.test_world_static`: **3 pruebas aprobadas**, limitadas al catálogo/snapshot/clasificador. No validan UI, recetas, XP ni consumo. Permanecen pendientes ejecución válida, material insuficiente, cantidad inválida, inventario lleno, cancelación, doble petición, desconexión y mesa portátil. Issue abierto; ningún fix aplicado.

## Fuente concreta de recetas y modalidad con artesano

Se ejecutó `RecipeCatalogProbe` con el lector nativo `apw` y `aNh`, usando únicamente el bdata de la instalación privada. Resultado: **5.449 recetas**, 34.049 filas de ingredientes y 5.449 filas de productos. El loader `bag.a(aNh)` construye `eTx`; no se necesita inventar un catálogo ni copiar assets al repositorio público. La extracción completa debe permanecer privada y ser reproducible con los archivos que aporte cada usuario.

Ejemplo verificado: receta **2047**, oficio 40, nivel 0; ingredientes item 2279 ×1 y 2340 ×5, producto 8047 ×4. Los ingredientes incluyen un tercer campo (`aNi.cvm()`), con valores 1 y 0 en ese ejemplo: no se ha resuelto su significado y no debe descartarse en el importador. El campo temporal bruto es 1000 (`aNh.Tz()` → `eTx.fKa()`); `eTx.av()` aplica un modificador del personaje, de modo que usar siempre ese valor como duración final sería incompleto. Esta receta no se ha producido en vivo ni se han confirmado sus nombres localizados.

La modalidad de 13515 se acotó: `boA.dBh()` compara el ID local (`aTJ.xl()`) con `iKq`; `boA.dBV()` busca `iKq` como personaje `bjo`. Es la rama con otro artesano, no simplemente una receta ordinaria con más bytes. `boQ.dCv()` consulta el oficio del artesano mediante `eTo.a(receta,boolean)` y convierte su resultado i32 a i64; todavía falta resolver la regla concreta del valor (no se le atribuye un coste en kamas sin verificarla). El servidor debe validar ambos personajes y condiciones vigentes, sin aceptar el valor declarado por el cliente como autoridad.

El probe anterior usaba dirección `client` y devolvía `None`; se repitió con la dirección real del codec, **`out`**. 12231 decodifica mesa 31515 / receta sintética 123 / cantidad 2 correctamente. 13515 devuelve `None`, sin rama de decodificación. Ambos carecen de handler en el dispatcher inspeccionado. El error del harness no se presenta como fallo del servidor.

## Definiciones nativas de mesa y receta

`sniffer/java/ExportRecipes.java` exporta ahora también el registro nativo `CRAFT_IE_PARAM` (`aKM`), su transformación (`baL` → `bFv`) y las 330 instancias `CraftTable` del catálogo de mapas. La compilación/ejecución offline en Docker produjo 5.449 recetas, 79 definiciones y 330/330 instancias resueltas, sin errores de lectura. El artefacto reproducible es `server/protocol/craft-recipes.json`; el exportador conserva `bBK` como dato bruto porque su significado sigue sin confirmarse.

El recorrido de bytecode distingue campos que antes se confundían: el parámetro textual de `CraftTable` (`bAp.dSG()`) es `definition_id`; `aKM.ckK()` pasa a `bFv.clx()` y selecciona la familia de estación (`fyB.aae()`); `aKM.ckL()` pasa a `bFv.cmG()` y el chequeo de disponibilidad lo entrega a `eTo.tW()` como oficio del personaje; `aKM.cmM()` pasa a `bFv.ged()` y `bAp.GE(recipeId)` / `bAp.i(recipeId, mode)` comprueban pertenencia a esa lista de recetas permitidas. Por tanto, “81” en el parámetro es una clave de definición, no el oficio 81. Por ejemplo, la definición 81 indica oficio 73, familia 77 y lista permitida vacía.

La validación cruzada conserva anomalías del origen en lugar de corregirlas implícitamente: cuatro definiciones tienen lista vacía (81, 138, 139, 191); 2.019 entradas de las listas no aparecen entre las recetas exportadas; y el ID de receta 10153 aparece en las definiciones 94 y 154 con oficio de tabla 81, pero oficio de receta 76. Esto puede indicar registros asociados a otro conjunto/dominio o datos incompletos; la exportación no prueba por sí sola que esas recetas se puedan ejecutar en cada estación. Las filas de receta incluyen el oficio y nivel mínimo, ingredientes, productos y duración cruda para que el consumidor del catálogo pueda validarlos. El campo adicional `aNi.cvm()` de los ingredientes sigue preservado sin atribuirle semántica.
