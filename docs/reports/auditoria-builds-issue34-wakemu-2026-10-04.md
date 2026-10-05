# Auditoría profunda del issue 34: builds personalizadas

Fecha: 4 de octubre de 2026. Solo investigación y propuestas del servidor; ninguna corrección aplicada.

## Conclusión técnica

El problema no es únicamente habilitar un botón al nivel 50. Existen fallos independientes: actualización incompleta al subir de nivel; índices de builds anunciados sin registros completos; activación sin handler; ausencia de selección persistida; estadísticas y combate que siguen usando la build 0. Guardar correctamente una hoja no demuestra que pueda seleccionarse, activarse o usarse en combate.

## Qué significa cada operación

Una build agrupa **cuatro hojas**: metadatos (nombre, índice, icono y nivel), equipo (UIDs/slots), aptitudes (puntos) y deck (hechizos/pasivos). Abrir o resaltar una fila cambia la build que se está editando; activarla decide qué hojas gobiernan al personaje. Guardar persiste lo editado, pero no debe confundirse con activar. El nombre visible Build 2 identifica aquí el índice 1: el índice 0 es Build por defecto.

El flujo esperado es: recibir colecciones completas → elegir fila y mostrar sus hojas → editar/guardar → activar → aplicar equipo, aptitudes y deck coherentes → conservar la selección tras reconexión. El fallo gráfico inicial ocurre al cargar las hojas de la fila, antes de poder demostrar una activación secundaria completa. El handler de activación ausente y el deck 0 fijo son defectos posteriores independientes.

## Entorno y método

Se usaron bases temporales y personajes nuevos para la matriz de backend, con SQLite y `BuildJournal` sobre `MemoryRedis`. También se ejecutaron pruebas de journal con Redis real usando claves de prueba únicas y SQLite temporal; no se editaron las claves del mundo activo.

Por autorización del usuario se creó el contenedor independiente `wakfu-builds-audit-20261004`: mundo `127.0.0.1:15566`, dispatcher `:15568`, API `:18091`. Usa SQLite nuevo, sin Redis compartido, y una copia fija del código/catálogos en `.runtime/local/instances/audit-builds-server-20261004/snapshot/`, montada en lectura. Su manifiesto SHA-256 está en `snapshot-sha256.json`; boot observado `f791df72d5e143218dc0c8c351a8d587`. No se reinició el servidor del otro agente ni se modificó su código.

La prueba gráfica usa el único personaje de esa instancia, **Audit Builds, ID 1**, Sacrógrito, perfil `audit-builds-isolated-20261004`. El personaje Audit Builds ID 12 del servidor original se usó solo para un baseline nivel 1; no confundir los IDs. Los cambios de endpoint fueron configuración de ese perfil y un wrapper privado del lanzador para la prueba, no correcciones del cliente ni cambios en sus fuentes/assets. Todos los objetos, tokens, capturas y datos generados permanecen en `.runtime`, excluidos de Git.

## 1. Cruce del nivel 50 sin reconexión

**Reproducido gráficamente:** después de `!nivel 49` y `!nivel 50`, el panel de builds conserva el candado y el texto «Las builds personalizadas están disponibles a partir del nivel 50». Cerrar y reabrir el panel no desbloquea la función. El panel de personaje sí muestra nivel 50, 550 PdV, PA 6, PM 3 y PW 6. Durante el ensayo también se observó HUD de nivel atrasado respecto al panel.

Capturas privadas: `level49-builds-spells.png`, `level50-before-reopen.png` y `level50-character-panel.png`. El texto observado acredita el umbral presentado por esta instalación, sin confundirlo con los niveles de desbloqueo de slots pasivos ni con los presets de nivel modulado.

**Confirmado en backend:** `maps/test_console.py::execute` actualiza nivel y XP, pero emite solo `13046` mediante `outside_progression`. El propio comando responde «vuelve a seleccionar el personaje para actualizar sus hechizos y puntos». La matriz probó niveles 49, 50, 51 y 60; todos conservaron esa única notificación. No actualiza el inventario de hechizos ni todas las colecciones de builds. La subida por combate tiene otra ruta (`combat_xp_gain`); no se debe extrapolar automáticamente el resultado gráfico del comando a toda subida por XP.

**Propuesta:** servicio común de progresión que determine los desbloqueos nuevos y emita los mensajes de inventario/colecciones nativos coherentes además de nivel/XP/estadísticas, tanto para recompensa como para comando administrativo. No reenviar una entidad parcial ni exigir reconexión.

### Repetición solicitada en nivel 100 y reconexión

Se subió únicamente Audit Builds ID 1 a **nivel 100**. Antes de reconectar, su ficha mostró nivel 100 y **1.050 PdV**, mientras el HUD conservaba 50, los slots seguían limitados y las builds personalizadas continuaban bloqueadas. Tras cerrar/reabrir solo este cliente y seleccionar de nuevo el personaje, el HUD mostró 100, se desbloquearon los slots correspondientes y apareció **Build 2**, con botón Nuevo y contador Builds (1/24). En una reconexión previa al nivel 50 el candado había persistido. Estos puntos no establecen el umbral efectivo exacto: falta acotar niveles intermedios y la configuración nativa que controla disponibilidad.

**Selección reproducida en la interfaz:** clicar Build 2 resaltó su fila, pero el título y los hechizos conservaron Build por defecto. Cambiar a Características/Equipables dejó el área de equipo vacía. El registro del cliente produjo `NullPointerException: Cannot invoke "bIR.dZu()" because "this.jFr" is null`, con ruta `byl.a → byp.dRp → byp.dRj → byp.Gw → dbU.M`, y posteriormente otra excepción en `byl.eH` durante el render. El evento incluye `BuildSheetModel{m_name='Build 2', m_level=-1, m_index=1}`: el nombre visible Build 2 corresponde al índice **1**, no al 2. El bytecode de `byl` confirma que `jFr` contiene el modelo de equipo y desreferencia `bIR.dZu()`.

Esto vincula el síntoma gráfico con la colección de equipo incompleta que también se comprobó mediante el parser nativo. La propuesta sigue siendo emitir desde el **servidor** hojas completas por cada índice anunciado. No se propone parchear la excepción del cliente. En esta secuencia no se registró opcode 13776; la selección falló antes de completar una activación secundaria. Por tanto, su handler ausente sigue siendo un hallazgo de código/protocolo, no una activación gráfica completada. Tampoco se atribuye a esta prueba un cast en combate con build secundaria.

Capturas y registro privados: `level100-live-builds.png`, `level100-reconnected-builds.png`, `level100-build2-empty-equipment.png` y `level100-build2-selection-errors.txt`, bajo `.runtime/local/instances/audit-builds-isolated-20261004/`. El servidor aislado mantuvo el mismo boot; no se reinició ningún servidor para esta repetición.

## 2. Colecciones inconsistentes antes de guardar

Se decodificaron los payloads generados para personajes nuevos en niveles 1, 49, 50, 51 y 200, en ambos backends:

| Colección | Índices emitidos |
| --- | --- |
| Metadatos de builds (`build_set`) | 0, 1 |
| Registro de equipo (`equipment_registry`) | 0 |
| Registro de aptitudes (`aptitude_registry`) | 0, 1 |
| Colección de decks (`deck_collection`) | 0 |

La build 1 puede aparecer anunciada sin equipo/deck registrado. El resultado es independiente del nivel en esas funciones; no implementan por sí mismas un desbloqueo al 50. Guardar builds 1 y 2 con contenido sí hizo que la reconexión generase índices 0/1/2 en equipo y decks. No afirmar que todas las builds guardadas carecen de hojas.

**Confirmación con el JAR nativo:** se generaron los mismos payloads de metadatos, registro de equipo y decks y se decodificaron mediante `eQV.ez`, `fpi.eO` y `fzg.gE`. El probe obtuvo build 1 existente, equipo 1 `null` y deck 1 `null`; equipo/deck 0 sí presentes. No es únicamente una interpretación del protobuf en Python. Fixture y probe privados: `BuildCollectionsProbe.java` y `build-native-*.bin`; no se alteró el JAR ni se aplicó ningún cambio al cliente.

Otra prueba mostró que `equipment_set` reemplaza entradas existentes pero no incorpora una build 2 nueva si el conjunto original solo contenía 0. Se debe revisar cada carrier; corregir uno no garantiza consistencia global.

**Propuesta:** una fuente autoritativa para builds disponibles, activas y hojas por índice; cada índice anunciado debe tener equipo, aptitudes y deck nativos válidos aunque estén vacíos. Mantener el bootstrap y las actualizaciones en vivo equivalentes.

### Cómo reproducir la selección que falla

1. Usar un personaje nuevo sin filas en `character_builds`, con las colecciones actuales que anuncian índices 0/1.
2. Subirlo a 100 por la consola de pruebas y volver a seleccionar el personaje para refrescar el estado; en el ensayo se relanzó únicamente su cliente.
3. Abrir Hechizos (`S`) y clicar Build 2. Comprobar la fila resaltada frente al título/contenido; no asumir activación por el resaltado.
4. Abrir Equipables y consultar el log del mismo perfil: buscar `BuildSheetModel` índice 1 y excepción `this.jFr` nulo. Guardar captura y hora antes de otra acción.
5. Correlacionar el boot, la conexión y las solicitudes: la ausencia de 13776 en esa secuencia impide atribuir el resultado a un rechazo de activación recibido por el servidor.

**Impacto práctico:** corregir únicamente el desbloqueo deja una fila visible que no puede cargar su equipo. Corregir únicamente el guardado puede hacer que una hoja exista en SQL, pero no corrige la build activa persistida ni el deck usado en combate. El número de builds permitido también requiere coherencia: la interfaz observada muestra capacidad **24**, mientras `builds.validate` acepta únicamente índices **0–2**. Se confirmó el rechazo del 3 en las pruebas de backend; no se creó gráficamente una tercera secundaria para atribuirle un mensaje concreto.

## 3. Guardar y activar son protocolos diferentes

El bytecode instalado confirma `cnR → 12772` para guardar cuatro secciones y `ctU/cER → 12284` para su respuesta. Esa respuesta aplica los blobs en sus registros; no implica seleccionar una build activa.

La ruta `dbU.P/M → c(long,byte)` construye `cnN`, opcode **13776**, con i64 del personaje y byte del índice (payload de 9 bytes). El dispatcher revisado no tiene handler para `13776`. La selección local puede cambiar temporalmente, pero falta la transición autoritativa del servidor.

También se identificó `cnO → 13169` para borrar, sin handler en ese dispatcher. Su respuesta nativa `cnP/cEN → 12837` muestra mensaje `build.deleted`; **es eliminación, no ACK de activación**. No reutilizarla para contestar 13776. `cEN` y `cER` restauran `heroBuildLock` en sus respectivos flujos; una ruta de borrado ignorada podría dejar controles bloqueados. Esto último requiere reproducción específica y no se atribuye al síntoma original sin evidencia.

**Propuesta:** implementar y validar la activación nativa propia, con ID/ownership/lease, índice existente, fase permitida y selección autoritativa; investigar su respuesta exacta y restauración ante rechazo. Mantener creación/guardado/activación/borrado como transiciones distintas e idempotentes. No enviar un opcode de respuesta por parecido de campos.

### Prueba controlada posterior: hojas completas y activación real

Se guardaron únicamente datos de prueba para Audit Builds ID 1: índice 1 llamado **Audit Complete**, nivel `-1`, equipo vacío nativo (12 bytes), deck predeterminado (36 bytes) y aptitudes vacías nativas (11 bytes). Se usó `Store.save_build` y la lease vigente; no se modificó código ni se agregaron objetos. El equipo vacío es una hoja existente, distinta de no enviar esa hoja. Tras relanzar solo el cliente, seleccionar Audit Complete cambió correctamente el título y mostró el deck. Equipables mostró personaje y slots vacíos normales: dejó de fallar por `jFr` ausente. La comparación modifica conjuntamente las hojas, por lo que no aísla todos los campos; el probe nativo y la excepción previa identifican específicamente la hoja de equipo ausente.

Al pulsar **Activar**, la interfaz marcó Audit Complete como Activa. El servidor registró a **18:09:57 UTC** solicitud `13776`, payload de **9 bytes**, personaje autenticado/cargado nivel 100 y build guardada `[1]`; la rechazó con **“No handler for this opcode in the current session state”**. Request ID `17e713dfe2034cf4a9cbaa52e892c37f`, mismo boot del servidor aislado. No se registró respuesta de activación ni cambio autoritativo en esa solicitud. Es una reproducción gráfica y de red del handler ausente, ya no solo lectura de código.

Después se usó Menú → Cambiar de personaje → Sí → jugar de nuevo con el mismo Audit Builds. La hoja Audit Complete siguió existiendo, pero **Build por defecto volvió a figurar Activa**. Esto reproduce la diferencia entre selección optimista local y selección del bootstrap. No prueba aplicación de bonus secundarios, porque las hojas de este ensayo tienen equipo y aptitudes vacíos; esa diferencia numérica sigue sustentada por la matriz controlada del apartado 4. Tampoco se realizó un cast con deck distinto en este ensayo.

Artefactos privados: `complete-build-selected.png`, `complete-build-equipment.png`, `complete-build-local-active.png`, `complete-build-reselect-default-active.png` en el perfil aislado, y `review-context/activation-live-log.json` en la carpeta de auditoría. La credencial API de prueba caducó durante una relanzada y se renovó únicamente para esta cuenta; ese intento de arranque no se atribuye al sistema de builds. El personaje queda en nivel 100 con esa hoja de prueba guardada para inspección.

## 4. Build activa no persistida y estadísticas de la build 0

`Store.character` carga hojas guardadas pero no `active_build_index`; no se encontró campo ni mutación persistida de selección. `equipment_stats.bonuses` y `aptitudes.bonuses` usan `character.get('active_build_index', 0)`. El propio módulo de equipo advierte que no hay activación persistida. `build_set` emite siempre índice activo 0, incluso si se le entrega un diccionario con índice activo 2.

**Prueba controlada:** personaje nivel 51, amuleto 2021 propio y unitario, una aptitud de +% PdV y un deck distinto guardados en builds 1 y 2:

| Medida | Evaluación normal | Índice secundario explícito |
| --- | --- | --- |
| UID equipado | Ninguno | Amuleto propio |
| Bonus plano de AP | 0 | +1 |
| Máximo de PdV | 560 | 588 |

Los 588 PdV incluyen el bonus plano del equipo y la aptitud; no atribuir toda la diferencia al amuleto. Guardar la build secundaria respondió `12284` y `13046`, pero el refresco utiliza la evaluación normal. Las hojas persistieron en SQLite y en el journal, antes/después de nueva generación de sesión, flush y reapertura del backend. La selección siguió ausente. Añadir índice activo 2 solo al diccionario de prueba aplicó sus efectos, pero recargar con `Store.character` volvió a la evaluación 0.

**Propuesta:** persistir la selección y versionarla; resolver equipo, aptitudes y deck desde el mismo índice. Activar con validación transaccional y recalcular HP/AP/MP/efectos sin duplicar bonus ni curar injustificadamente; conservar la selección tras guardar, reconectar o recuperar el proceso.

## 5. El combate usa explícitamente el deck 0

En `local_game_server.py`, la preparación de listo y la ejecución de `13260` leen `builds.get(0, {}).get('deck')`, usando deck predeterminado si falta. No consultan un índice activo. En la matriz, la build secundaria tenía el hechizo 5047 y no había deck 0 guardado; el servidor elegiría el predeterminado, aunque el usuario viese el deck secundario.

Esto está confirmado por código y datos; no se efectuó todavía un lanzamiento gráfico para atribuir su rechazo a esa diferencia. `server_runtime` construye la autoridad de hechizos desde el deck recibido, por lo que corregir solo la selección visual no cambia la autorización de combate.

**Propuesta:** usar un resolver único de build activa en bootstrap, estadísticas, inicialización y cast. Fijar y versionar la build del encuentro; rechazar cambios incompatibles durante combate sin alterar recursos ni enviar resultados parciales.

## 6. Límite de nivel y representación de hojas vacías

**Reproducido:** una hoja de aptitudes de build 0 guardada válidamente con nivel fijo 49 produce `Invalid aptitude sheet level` al cargar/evaluar después de subir el personaje a 50. Ocurre en SQLite y en el journal; este último evalúa el estado en `overlay`, por lo que puede fallar durante la hidratación. Con nivel de hoja `-1` se usa el nivel actual y no se presenta ese caso en la matriz principal.

**Prueba adicional del comando completo sobre la copia fija:** guardar esa hoja 49 y ejecutar `!nivel 50` produce el mismo error después de confirmar nivel/XP. La consulta SQL posterior muestra nivel **50**, HP **540** y máximo **540**, en vez del máximo base 550 de ese Sacrógrito al nivel 50. El recalculo posterior falla y no revierte el cambio previo. La fixture y su BD temporal fueron eliminadas al terminar; resultado privado en `builds-levelup-atomicity-result.json`. La futura corrección debe definir una transición coherente de nivel/hojas/salud, validando antes de confirmar o recuperando explícitamente; no dejar un cambio parcialmente aplicado.

La validación de metadatos y aptitudes admite solo `-1` o el nivel actual, mientras el deck admite un cap inferior. Revisar si la hoja debía seguir el nivel real o ser una build modulada antes de cambiar reglas. No aceptar sin control presupuestos/equipo de nivel superior ni migrar toda hoja limitada a nivel actual perdiendo su intención.

**Confirmado:** blob `b''` en un guardado significa conservar la sección anterior; para vaciar se requieren representaciones nativas explícitas (`EMPTY_EQUIPMENT`, `EMPTY_APTITUDES`, deck codificado vacío). Se probaron ambas: enviar cero bytes preservó el equipo; enviar protobuf vacío válido lo retiró. Documentar esa semántica y verificar el paquete real de cada editor antes de diagnosticar un borrado fallido.

## Pruebas ejecutadas y límites

- Suite enfocada: 50 tests descubiertos, **40 ejecutados OK y 10 omitidos** porque requerían Redis real.
- Journal sobre Redis real: 10 descubiertos, **9 ejecutados OK y 1 omitido** porque la inyección de caída solo admite el doble en memoria. Claves de prueba únicas, limpieza propia, sin reiniciar Redis.
- Experimentos adicionales: **44 filas de evidencia** de matriz y casos límite, más una prueba del comando completo de subida con hoja fija, con assertions posteriores sobre los resultados; son pruebas diagnósticas de defectos existentes, no regresiones que demuestren corrección.
- Rechazos comprobados en ambos backends: índice 3, UID ajeno/inexistente, deck de otra clase y aptitudes sobre presupuesto; todos conservaron las hojas previas. La autoridad básica de guardado funciona en esos casos.

Los tests existentes ejercitan persistencia, ACK, ownership y cálculos aislados, pero no prueban una transición exitosa completa 13776 → selección persistida → estadísticas/deck → reconexión. La prueba posterior sí reprodujo el rechazo real de 13776 y el retorno visual a la build 0 al volver a seleccionar el personaje. Artefactos privados en `.runtime/local/instances/audit-20261004/`: `audit-builds-matrix.py`, `builds-matrix-results.json`, `audit-builds-boundaries.py`, `builds-boundaries-results.json` y bytecode `build-*.txt`. No se modificaron tests o fuentes del proyecto para esta auditoría.

## Criterios para una futura corrección

La aceptación requiere comprobar el umbral/configuración nativa que anuncia 50 y sincronizar el desbloqueo al cruzarlo por XP y comando; colecciones completas antes de guardar; creación/guardado/activación de builds 1/2; efectos y deck coherentes al alternar; selección conservada al reconectar; hojas limitadas y vacías correctas; rechazo sin bloquear controles; y pruebas de combate con un hechizo presente exclusivamente en la build seleccionada. Añadir casos de HP parcial, equipo compartido entre hojas, presupuesto de aptitudes, sesión reemplazada, duplicación de solicitudes y recuperación del journal. Ninguna de estas soluciones se implementó.
