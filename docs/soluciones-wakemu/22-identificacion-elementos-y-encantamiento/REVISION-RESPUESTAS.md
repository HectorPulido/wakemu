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

El dispatcher inspeccionado no tiene 13787 ni 12487. `inventory_item_elements` mantiene máscaras por UID, pero no apareció un dominio persistido equivalente de `fpI` para engastes. Los grants nuevos sortean máscaras; los objetos antiguos sin metadata no se hidratan con una selección inventada. Esto explica por qué una mejora parcial de elementos no certifica el recorrido solicitado.

Implementar por separado identificación inicial y selección; validar propiedad, nivel, inventario y combate antes de mutar. Persistir el resultado individual antes de 13766 y resolver reintentos con ese mismo resultado. Para stacks, separar una unidad y asignar su UID/metadata sin duplicar cantidad ni borrar el resto. Publicar actualización del objeto y del registro de equipo que lo referencia.

## Trabajo técnico aún abierto

Se resolvió el carrier de engastes: `fpK.e/eQ` serializa/decodifica `lD` protobuf. Falta cotejar distribución, cantidades, cargos de operación, reciclaje, devolución y compatibilidad de sublimaciones con esta versión. No convertir 7 cargas o 90% del contexto en fórmulas oficiales sin prueba. Completar respuesta negativa y prueba gráfica de doble clic, selección y reconexión. Estos puntos son investigación asignada al auditor: no se vuelven a pedir como decisiones del usuario. No se modificó código y no se continúan hechizos.

## Engastes: segunda prueba nativa ejecutada

El enum `QE` identifica rojo=1, verde=2, azul=3 y **blanco=4**, además de NONE=0. No hay amarillo en este enum de la versión instalada. El descriptor `lD` contiene shardSlots (1), additionalGems (2), sublimationItemId (3), specialSublimationItemId (4) y charges (9).

Se codificó y decodificó un objeto sintético con cuatro engastes, uno de cada color, y siete cargas; todos se preservan. Una respuesta 13766 con ese blob y sin blob elemental también se decodifica correctamente y mantiene ambos estados separados. [Prueba y bytes](probe-engastes-nativos.json). Los siete se eligieron como entrada de prueba: no demuestran que sacrificar conceda siete cargas ni una tasa de generación. El carrier tampoco acredita por sí solo bonus de sublimación.
