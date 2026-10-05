# Revisión de código y contrato — mesas de oficio

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
