# E14 — Persistencia de consumibles en accesos rápidos

## Síntoma y evidencia inicial

El usuario reporta que semillas, pan y otros consumibles asignados a la barra rápida desaparecen después de cerrar y volver a entrar. No se acredita que los objetos desaparezcan del inventario; el síntoma corresponde al acceso.

La revisión inicial encuentra la sección nativa `SHORTCUT_INVENTORIES` en `server/wakfu_server/wire.py`. No se encontró una implementación de dominio de barra rápida en la búsqueda de `shortcut`, `quickbar`, `hotbar` o `action_bar` del servidor. Esto orienta la inspección, pero no prueba por sí solo ausencia de handlers: deben identificarse opcodes y carriers nativos antes de concluir causa. No se han probado cambios gráficos ni guardado real.

## Investigación requerida

Capturar mediante Luna low la asignación y reconexión en personaje exclusivo de auditoría; identificar solicitud de alta, cambio y eliminación del acceso, ACK y bootstrap. Cotejar encoder y consumidor nativos y si la referencia es UID, referencia de objeto, tipo de acceso o combinación. No tocar accesos a hechizos ni su implementación, reservados a otra sesión. Comparar cierre normal, desconexión y nueva sesión.

Seguir la sección `SHORTCUT_INVENTORIES` desde serialización hasta su registro local y verificar si replay restaura un template capturado, vacío o estado autoritativo del personaje. Revisar SQL/journal y propiedad de referencia antes de diseñar una migración.

## Solución del servidor a concretar con protocolo

Persistir por personaje barra, posición, tipo y referencia nativa validada, con revisión y lease. Confirmar cambios antes del ACK y restaurar todos los accesos desde estado durable al entrar. No guardar un UID ajeno ni permitir que un acceso cree objetos. Definir reconciliación cuando se consume el último objeto, se divide/fusiona un stack o se cambia de contenedor, según el contrato nativo; no adivinar que referencia de catálogo equivale a UID.

Probar semillas y pan, varios slots/barras, sustitución, eliminación, reconexión, stack agotado y reintento. Ninguna solución aplicada; causa exacta y formato de mensajes pendientes de cotejo.

## Bootstrap actual: vaciado confirmado por código

`wire.EMPTY_SECTIONS` contiene `SHORTCUT_INVENTORIES`. Para personajes con nivel y una fixture de entidad cuyo hash coincide, `minimal_entity` recorre las secciones y sustituye esta por `ENTITY_DEFAULTS[name]`: actualmente **0000**. No existe una rama específica que consulte accesos guardados del personaje. La enumeración nativa `eHe` identifica esta sección como ordinal **18**.

Este cotejo confirma que el adaptador actual restaura la codificación vacía en esa sección, aunque la captura original contuviera accesos. Es una causa concreta de pérdida de restauración compatible con el síntoma del usuario. Aún no prueba el recorrido vivo exacto de su sesión ni identifica el mensaje de guardado: no se declara que todo acceso se persista en otro lugar o que el cliente no envíe cambios.

La solución debe sustituir esta rama vacía por serialización autoritativa de accesos consumibles, usando el contrato nativo completo de la sección. No basta con preservar los bytes de la captura: corresponderían a otro personaje/objetos. Antes de diseñar tabla y handlers, identificar estructura, tipo, UID/referencia y operaciones nativas; mantener límites y validación de propiedad. [Evidencia de fuentes](probe-bootstrap-vacio.json).

## Solicitud nativa de modificación identificada

El catálogo de mensajes observado ya contiene **12091 / cnE**, cliente→servidor. Su encoder actual escribe identidad i64, contador i16 de eliminaciones y claves i32, seguido de contador i16 de asignaciones y pares `clave i32 + descriptor yu`. `cnE.c(byte,byte,byte)` agrega eliminación; `cnE.a(byte,byte,byte,bOS)` agrega asignación. La clave se calcula `(primerByte << 16) + (segundoByte << 8) + tercerByte`: falta nombrar estos ejes desde su caller, no asumir que son inventario/barra/slot sin comprobarlo.

`yu` ocupa **17 bytes**: tipo byte (`Vg`), identidad long (`amg`), dos ints (`amh`, `ami`). Su decoder/encoder conserva esos cuatro campos. `bOS.a(yu)` los convierte a tipo `fyw` y datos de acceso. Esto demuestra que persistir únicamente un número de slot y referencia de objeto perdería parte del contrato. La semántica concreta del tipo consumible y de cada identidad continúa pendiente del caller y catálogo.

No se encontró **12091** en el dispatcher ni decoder Python actuales. Junto al bootstrap vacío, identifica dos brechas distintas: no restaurar accesos y no atender esta solicitud de modificación. La inspección es estática, con dumps privados; no se envió solicitud ni se atribuye al reporte una captura de 12091 todavía. Próximo paso: ejecutar fixture del encoder para consumibles una vez identificado `fyw`, validar límites de contadores y determinar si hay ACK o restauración únicamente vía entidad.

## Tipos de acceso y fixture nativa ejecutada

La enumeración `fyw` distingue **1 = USABLE_REFERENCE_ITEM** y **2 = ITEM**. `fyt.b(type,long,int,int)` trata el tipo 1 de forma especial: sustituye el long recibido por el primer int convertido a long. Para tipo 2 conserva el long original. Por tanto, un acceso por referencia utilizable no tiene la misma identidad que un acceso al objeto concreto. No exigir un UID de inventario a ambos tipos ni remapearlos indistintamente al dividir un stack.

Una fixture Java offline creó tipo 1 con long sintético 987654321, referencia 4275 y último campo −1. Al serializar resultó `(tipo1,long4275,int4275,int−1)`. Tipo 2 con los mismos argumentos conservó long **987654321**. El encoder `cnE` produjo una solicitud 12091 con una eliminación y una asignación; el cuerpo de **37 bytes** conservó personaje12345, claves010203/010204 y descriptor completo tras decodificar con `yu.aG`. [Resultados](probe-descriptor-consumible-nativo.json). No se enviaron paquetes al servidor ni se ejecutaron hechizos.

Esto permite proponer almacenamiento de tipo y campos nativos explícitos, conservando el descriptor en vez de reducir todo a UID. Falta cotejar el drag real de semillas/pan para acreditar qué tipo usa cada uno y nombrar el último int; no se infiere por el nombre del enum que toda semilla use tipo1. El servidor debe validar referencias permitidas para tipo1 y ownership de UID para tipo2, con reglas de disponibilidad acordes al consumidor.

## Ejes de posición y agrupación de cambios

El caller identificado es **`bOY.ekn()`**. Recorre sus barras, examina cambios y construye un único `cnE(character)` para las operaciones pendientes. Los tres bytes pasados al encoder son: **ordinal del tipo de barra `fyv`**, **índice de barra relativo al inicio de ese tipo**, **posición dentro de la barra**. `fyv` define **WORLD=0**, **FIGHT=1**, **SYMBIOT_BAR=2**. El índice relativo se calcula restando `fyv.ePn()` al índice global de la barra; no debe persistirse accidentalmente el índice global como número relativo.

La instalación declara WORLD con **8 posiciones × 4 barras**, FIGHT con **6 × 4** y SYMBIOT_BAR con **8 × 1**. Son límites del cliente instalado, distintos de tipos de acceso `fyw`. El registro del servidor debe validar ambos enums por separado. El alcance de implementación solicitado aquí es consumibles de WORLD; no habilita alterar decks/hechizos ni la barra FIGHT de la otra sesión.

Para cada barra modificada el caller agrega asignaciones y dos listas de eliminaciones, limpia el seguimiento local (`bOX.ejL`) y finalmente envía el mensaje agrupado. No se observó en este método una espera de ACK antes de limpiar los cambios. Si el servidor ignora 12091, no existe en esta ruta un reintento durable del cambio que lo recupere al reconectar. Deben verificarse callers/timing de `ekn` y respuesta de error antes de afirmar cuándo se envía durante cierre.

Propuesta concretada: clave DB `(character_id,bar_type,bar_number,slot)`, descriptor con `shortcut_type,long_value,int_value,extra_int` y revisión. Aplicar la lista completa de operaciones de un mensaje atómicamente; validar todas antes de modificar alguna. Contadores, claves repetidas y colisiones entre eliminación/asignación requieren semántica explícita cotejada con el caller. No interpretar ausencia de una posición en un delta como borrado global; restaurar la colección completa en el bootstrap nativo.

## Restauración de colección: orden de barras significativo

La estructura nativa completa es `so`, con contador **u16** y lista de `sq`; cada `sq` contiene `yv` (tipo byte, contador u16 y lista de entradas). `bOY.a(so)` mantiene un contador independiente por tipo de barra e inserta cada registro en la **siguiente barra de ese tipo según el orden de la lista**, comenzando por `fyv.ePn()`. No toma un número explícito de barra en `yv`. Al terminar limpia las barras no presentes.

Esto concreta una condición del serializer del servidor: si se quiere restaurar una asignación de WORLD barra 2 sin datos en barras 0/1, debe conservar los registros vacíos precedentes de ese tipo; omitirlos desplazaría la asignación hacia barra 0. Enviar una colección parcial puede limpiar barras que no venían en el snapshot. Validar cantidad por tipo antes de publicar: el consumidor indexa arrays usando los ordinales recibidos y no aporta una defensa completa contra tipos o cantidades fuera de límites.

La codificación `0000` significa cero registros y lleva precisamente al recorrido que limpia todas las barras. Queda pendiente la fixture de colección poblada y el consumidor dentro de GUI; el formato de entrada `yw` y su posición también deben cotejarse antes de implementar.

## Fixture de colección completa ejecutada

[Probe nativo](probe-coleccion-nativa.json): `so/sq/yv/yw/yu` serializaron y restauraron **30 bytes** con tres barras WORLD: primeras dos vacías y tercera con posición **3**, tipo **1**, referencia **4275**. Se conservó la lista, posición y descriptor; `0000` también se decodificó directamente y produjo cero barras. Cada entrada `yw` contiene **i16 posición + descriptor17**, es decir **19 bytes**. El contador de la colección y el de entradas por barra son u16; tipo de barra es byte.

Esta fixture acredita los codecs de restauración, pero todavía no el enlace entre sección de entidad y `bOY.a(so)`, ni drag/reconexión reales. La referencia4275 sirve como fixture de consumible por referencia; no atribuye ese tipo a una captura de semillas. El serializer debe preservar barras vacías precedentes y ordenar cada tipo por número relativo, conservando el estado completo autorizado.

## Enlace con entidad y consumidor ejecutado

El observador nativo **`biQ`** se registra sobre `so.DM()`. Su `zm()` obtiene `biB.iig` (barras del personaje), llama a **`bOY.a(so)`** y después a `bOY.c(eQW)` para contexto de builds. Esto identifica el enlace de restauración desde la estructura de entidad, además de los codecs aislados.

Se ejecutó **`bOY.a(so)`** sobre objetos nuevos privados: restauró WORLD barra **2**, slot **3**, referencia **4275**, comprobado mediante lookup nativo de esa barra y posición. Cargar a continuación `new so()` eliminó ese acceso del lookup. [Prueba del consumidor](probe-consumidor-restauracion.json). Ningún click ni cambio al cliente vivo; no se ejecutó GUI ni hechizos.

La brecha de bootstrap ya tiene evidencia de efecto en el consumidor: una colección vacía limpia accesos existentes. Continúan pendientes captura del drag real de semillas/pan, envío temporal de12091 y reconexión autenticada; no se afirma una prueba end-to-end por este consumidor offline.

### Límite comprobado del intento gráfico

Luna confirmó mundo cargado, inventario abierto y tooltip de semilla de cardo ×5. Antes de arrastrar, el inspector devolvió conexión rechazada y sus comprobaciones de proceso/listener no encontraron el cliente de auditoría. No se ejecutó el arrastre ni la reconexión; no se atribuye esta terminación al servidor ni al issue. Véase `probe-limite-cliente-grafico.json`. La prueba gráfica sigue pendiente y requiere preparar de nuevo el cliente aislado.

### Arrastre con cliente conectado: resultado no confirmado

Luna entró con Audit Builds nivel 100 y confirmó semilla de cardo ×5. Un arrastre a la casilla señalada devolvió `ok`, pero no mostró icono ni tooltip de acceso y el log aislado no registró 12091. No hubo reconexión; este intento no reproduce pérdida de persistencia. Que la pila siga ×5 es normal al crear un acceso y no se usa como prueba de error. Véase `probe-arrastre-grafico-no-confirmado.json`.


## Revalidación del cliente antes de repetir arrastre

Luna comprobó estado conectado de Audit Builds y screenshot privado a 02:51:36 UTC. Semillas visibles ×5; barra parcialmente tapada por inventario, sin asignación visible acreditada. El inspector informa canvas 1500×950 y PNG 2016×1248: las razones por eje no son idénticas; no asumir que un único factor transforma coordenadas correctamente. Se solicita despejar barra e identificar slot/bloqueo antes de otro intento. No se ha ejecutado reconexión ni confirmado el defecto de persistencia mediante esta UI. [Estado observado](probe-estado-grafico-actual.json).


## Segundo intento: límite de automatización confirmado

Luna confirmó tooltip «Semilla de cardo» y realizó **un** arrastre a la ranura previamente localizada, a 03:02:01 UTC. Inspector `ok`, pero sin icono/tooltip en destino; la consulta de registros JSON de la instancia propia encontró cero filas12091. No se reconectó porque no se consiguió asignación inicial acreditada. La pila ×5 no indica fracaso: asignar un acceso no consume unidades.

No repetir el mismo arrastre como si fuese una prueba nueva de persistencia. El siguiente paso exige cotejar caller/timing de modificación y captura saliente del cliente o una asignación manual confirmada; la reproducción automatizada actual no alcanza ese precondición. Esto no contradice el reporte del usuario ni demuestra que un jugador no pueda asignarlo. [Resultado](probe-segundo-arrastre-no-confirmado.json).


## Momento de envío: no inferir fallo desde ausencia inmediata de 12091

El escaneo ASM exacto encuentra cinco callers de `bOY.ekn`: `civ.b`, `dcQ.fgc`, `bya.B`, `biB.a` y `aTx.g`. En `dcQ.fgc`, si existe personaje, envía cambios antes de limpieza/pantalla `charactersLoading.progress` y de una solicitud `csM`. Esto acredita una ruta de flush vinculada a transición, no envío inmediato al arrastrar.

Por tanto, cero12091 durante el intento de drag **no basta para afirmar que el cambio no se produjo**; la falta de icono es el límite visual independiente. Una futura prueba debe confirmar primero asignación local, capturar salida y ejecutar transición controlada para observar flush. No cerrar bruscamente el proceso y atribuir al servidor cambios que nunca recibió. El reporte del usuario puede implicar cierre/reentrada, pero la semántica exacta de cierre debe registrarse. [Callers cotejados](probe-callers-envio-shortcuts.json).


## Callers restantes: límites de atribución

`civ.b` responde a `aAo`, evento interno cuyo `d()` devuelve −2147483648; no convertirlo en opcode de red. `biB.a(fcb)` ejecuta `drd → ekn` antes de delegar al modelo; `bya.B` lo hace bajo condición `fkH.gdy` antes de limpiar UI; `aTx.g(biB)` también llama `ekn`, pero falta seguir su enlace/caller de cierre. Estas rutas confirman varios puntos de flush; **no acreditan un temporizador periódico ni que el cierre forzado envíe cambios**.

En pruebas futuras registrar salida normal a selector, cierre normal y terminación abrupta como escenarios diferentes. El servidor solo puede persistir lo recibido: el contrato de restauración debe seguir funcionando aunque el lote nunca haya llegado, conservando el último estado confirmado. No afirmar que el protocolo instalado permite recuperar automáticamente cambios locales no enviados. [Contextos cotejados](probe-callers-envio-shortcuts.json).
