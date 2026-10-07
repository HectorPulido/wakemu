# Identificación: contratos y condición del signo de interrogación

## Hallazgos concretos

La UI nativa `cQi` vincula una capa `UnidentifiedItem` a `slotsIdentificationNeeded`. `bGl` resuelve esa propiedad con `fnR.ghe()`. La propiedad general `identificationNeeded` combina `ghe()` (engastes) y `ghf()` (elementos). Por tanto, guardar máscaras elementales no completa identificación de engastes ni garantiza quitar el signo. No se afirma haber inspeccionado todas las vistas que dibujan interrogaciones.

`ghe()` consulta las opciones `fpI` y la elegibilidad del template; `ghf()` comprueba si el template tiene elementos variables y falta `foX` o está vacío. Hay que respetar elegibilidad por plantilla: no generar engastes para todos los objetos ni dar por hecho que toda interrogación significa ausencia de elementos.

## Peticiones y respuesta verificadas

| Operación | Opcode | Cuerpo |
| --- | --- | --- |
| Sorteo/identificación inicial | 13787 (`cpY`) | i64 UID, 8 bytes |
| Selección de elementos | 12487 (`cpZ`) | i64 UID + byte máscara de daño + byte máscara de resistencia, 10 bytes |
| Resultado de identificación | 13766 (`cxh`) | Estado, UID y blobs independientes de elementos y engastes |

`19306` es un evento **interno** de la UI que `dcu` transforma en `cpY`; no es el opcode para implementar en la red. `cZI` separa la ruta de selección manual/automática y la inicial según el template y modo. El doble clic debe seguir esa ruta; no interpretarlo como uso genérico de consumible.

Se ejecutaron los encoders nativos para UID sintético 12345 y se decodificó una respuesta con elementos pero sin engastes. El decoder acepta status OK y distingue los dos estados. Truncar un byte produce BufferUnderflowException. [Frames sintéticos y resultados](probe-identificacion-nativa.json).

## Qué falta en el servidor

El dispatcher inspeccionado no tiene 13787 ni 12487. `inventory_item_elements` mantiene máscaras por UID. Se añadió la persistencia aislada `inventory_item_shards` para `fpI` mediante el protobuf `lD/ProtoShard`; eso conserva estado ya producido, pero no implementa generación. Los grants antiguos sin metadata no se hidratan con selecciones elementales ni engastes inventados.

Implementar por separado identificación inicial y selección; validar propiedad, nivel, inventario y combate antes de mutar. Persistir el resultado individual antes de 13766 y resolver reintentos con ese mismo resultado. Para stacks, separar una unidad y asignar su UID/metadata sin duplicar cantidad ni borrar el resto. Publicar actualización del objeto y del registro de equipo que lo referencia.

## Trabajo técnico aún abierto

Se resolvió el carrier de engastes: `fpK.e/eQ` serializa/decodifica `lD` protobuf. Falta cotejar distribución, cantidades, cargos de operación, reciclaje, devolución y compatibilidad de sublimaciones con esta versión. No convertir 7 cargas o 90% del contexto en fórmulas oficiales sin prueba. Completar respuesta negativa y prueba gráfica de doble clic, selección y reconexión. Estos puntos son investigación asignada al auditor: no se vuelven a pedir como decisiones del usuario. No se modificó código y no se continúan hechizos.

## Autoridad aislada para 12487

`wakfu_server.element_selection` implementa el SET de máscaras elementales, restringido a las cardinalidades del template y a un UID de inventario propio. La UI nativa invoca `cZI.a(item, dialog)` cuando `ghe() OR ghf()` es verdadero; el consumidor de 13766 llama a `fnR.a(foX)` para aplicar los elementos recibidos. Por eso una nueva máscara válida puede reemplazar la existente mientras el objeto requiera identificación por otra propiedad; el recibo conserva el último SET y el reintento idéntico no muta.

El decoder de 13766 produce `null` para un blob de sockets con longitud cero. El consumidor solo reemplaza `fnR.fpI` si el blob no es nulo. La migración 050 guarda el blob nativo por UID; `inventory_items.load` lo hidrata, `item_proto` lo emite como `ProtoItem.shard` (campo 52/tag 418) y `item_form` lo convierte al formato de inventario `vA` (`yp`). No se envía 12471 como reemplazo de la misma unidad. La copia de metadatos de intercambio conserva el estado; movimiento parcial y merge rechazan ítems que ya tengan estado de sockets.

El mapeo de tipos se confirmó con el descriptor Java instalado: `lD` es `ProtoShard`; sus campos son `shardSlots` 1, `additionalGems` 2, `sublimationItemId` 3, `specialSublimationItemId` 4 y `charges` 9. El codec `fpK.e/eQ` usa exactamente ese protobuf. El formato `yp.aF/aG` se contrastó en `vA` y `vj`; el probe Java consumió un `item_form` generado por Python y recuperó el mismo `ProtoShard` con un slot, adicional, IDs de sublimación y cargas.

El export nativo sobre las 20.230 definiciones de objetos encontró 9.163 elegibles para `fpC.gjv()`; el método solo verifica que `cpR` y `cpS` sean distintos de cero. Los bounds usados por `fpK` limitan la cantidad elegida entre esos valores. Un análisis de callsites no halló que la utilidad `fpK.cT/cV` se invoque desde el flujo cliente-servidor de 13787, por lo que su distribución no queda acreditada como regla original. `shard_identification.py` aplica sus pesos como política local configurable, con costo local 0 y gate por nivel del objeto; guarda el resultado y recibo idempotente en la misma transacción. No hay soporte para stacks ni para fabricar el status de espacio libre sin el contrato nativo de split. La migración 053 y la autoridad siguen sin despliegue; falta integración dispatcher/13766, respuesta visual y prueba de extremo a extremo.

Validación aislada: `test_inventory_elements` pasó 5/5 en PostgreSQL, cubriendo codec, template, reintento/cambio, persistencia, propiedad, stack, equipo e intercambio. No se conectó al dispatcher ni se desplegó.

## Engastes: segunda prueba nativa ejecutada

El enum `QE` identifica rojo=1, verde=2, azul=3 y **blanco=4**, además de NONE=0. No hay amarillo en este enum de la versión instalada. El descriptor `lD` contiene shardSlots (1), additionalGems (2), sublimationItemId (3), specialSublimationItemId (4) y charges (9).

Se codificó y decodificó un objeto sintético con cuatro engastes, uno de cada color, y siete cargas; todos se preservan. Una respuesta 13766 con ese blob y sin blob elemental también se decodifica correctamente y mantiene ambos estados separados. [Prueba y bytes](probe-engastes-nativos.json). Los siete se eligieron como entrada de prueba: no demuestran que sacrificar conceda siete cargas ni una tasa de generación. El carrier tampoco acredita por sí solo bonus de sublimación.
