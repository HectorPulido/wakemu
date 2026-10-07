# Pasaporte: superficies nativas y estado actual

## El pasaporte es una interfaz comprobada

Inspección offline del cliente instalado: `PassportCommand` activa/desactiva el frame `ddU`; este abre **`passportDialog`** y registra los controles **`wakfu.passport` → `cMC`**. Inicializa `passportViewMode` y `passportCategory` a cero, `secrets` con `bOP` y el componente de ranking mediante `bMO.a(personaje,false)`. Esto identifica directamente el widget pedido; **no hay que pedir al usuario una referencia de item para investigar esta ventana**. `bOP` administra páginas de secretos, no el identificador de nación.

Falta seguir el binding nacional concreto del diálogo y verlo en el personaje de auditoría: identificar la ventana no acredita qué texto/icono está mostrando actualmente ni descarta otros widgets que mencionen el pasaporte.

## El código actual ya sustituye parte de la captura

`wire.minimal_entity()` reemplaza **NATION_ID y CHARACTER_LIST_NATION_ID por i32 0**; NATION_SYNCHRO por 27 ceros. Solo opera con nivel presente y layouts reconocidos; verifica el hash de plantilla antes de aplicar límites de sección. **No es correcto afirmar que esa ruta actual envía siempre Amakna.** El reemplazo tampoco implementa ciudadanía elegible o persistida: publica ausencia de nación mientras no exista un modelo local autorizado.

`social.company()` publica nación 0 y XP inicial 1. `social.adapt(15984)` reemplaza exclusivamente registros regionales formato 17 por ID de región +49 ceros; conserva los otros registros y sus IDs. Vaciar el gobierno capturado no convierte a todos los territorios en neutrales. Deben mantenerse separados ciudadanía del personaje, nación de la compañía, gobierno público y propietario territorial.

## Solución concreta del servidor

Seguir el binding del diálogo hasta el carrier exacto que alimenta nombre/icono. Comparar el bootstrap real con estas rutas, su selección de layout y su adaptación; localizar cualquier replay que aún conserve nación del personaje capturado antes de añadir otro parche. Validar datos de origen del personaje y persistir ciudadanía propia cuando exista ese sistema; la nación no debe inferirse automáticamente de la posición actual. Una transición de mapa actualiza contexto territorial, no cambia por sí sola el pasaporte.

Conservar ID de territorio y metadatos nativos necesarios para ecología/bonus; reemplazar únicamente datos de captura ajenos con estado propio. No borrar indiscriminadamente 15984: contiene registros regionales de otras clases. Extender fixtures y serializers reconocidos, respetando ancho i32 y validación de identidad, para publicar la nación propia cuando se implemente.

## Pruebas ejecutadas y límites

`PYTHONPATH=server python3 -m unittest tests.test_social tests.test_wire`: **29 pruebas aprobadas**. Incluyen identidad de compañía, eliminación de gobierno heredado y conservación de regiones ajenas al formato nacional. No prueban el texto de `passportDialog`, ciudadanía futura ni origen del personaje. No se ha reproducido el pasaporte Amakna en el cliente durante esta revisión; queda pendiente cotejar captura propia y UI mediante Luna. No se aplicó ningún fix y el issue permanece abierto.

## Intento GUI con Luna: resultado negativo explícito

Perfil propio `audit-builds-isolated-20261004`, personaje Audit Builds nivel 100. Luna comprobó inspector/ventana y cerró inventario mediante tecla i. Intentó identificar un acceso secundario, pero abrió **Enciclopedia** (Bestiario/Equipables/Objetos), no `passportDialog`. Al cerrar mediante un click de X, el click se propagó al mundo y el personaje pasó de (-3,0,0) a (-5,-11,0).

No se obtuvo captura ni lectura del pasaporte. **No se confirma Amakna ni neutralidad visual** con este intento. El movimiento accidental se registra como incidente del procedimiento instrumentado, sin atribuirlo al pasaporte o al servidor. Se indicó dejar de clicar cierres/iconos no acreditados y priorizar entrada del segundo cliente; todavía se necesita una ruta UI identificada para la reproducción.

## Evidencia visual adicional: selección del segundo personaje

Luna llegó a selección del segundo perfil `audit-multi-dos-isolated-20261004`. La ficha única ocupada mostró **Audit Multi Dos — Uginak — nivel 1 — Amakna**. Es un personaje recién creado en la cuenta propia de auditoría; no se observó `passportDialog`. El resultado confirma el texto nacional en **selección de personaje**, y exige contrastar el payload realmente recibido con el reemplazo NATION_ID actual. No se concluye todavía que la DB guarde ciudadanía Amakna: puede ser versión cargada, layout no adaptado o representación de nación cero; esas hipótesis necesitan cotejo.

## Cotejo PostgreSQL y parser nativo — 2026-10-05

La plantilla de producción se obtiene con `character_list_local`, que selecciona el único blob que contiene Pekebu dentro del fixture23548. Mide301 bytes y su SHA256 es `6de50d9932ae0be8dcbee826826707c25bcb6a517980c5ed0c45de9473ed13f3`, coincidente con `ENTITY_LAYOUTS[5]`. El primer blob del roster completo no sustituye esa plantilla.

En PostgreSQL aislado se creó un personaje y se serializó `store.characters` con `wire.character_list` y la plantilla correcta. La entidad resultante medía193 bytes; su qZ apareció en offset173 después de compactar las secciones previas, con bytes `00000000`. El probe Java offline de `qZ.aG` confirmó `parse=true`, `Wi=0`. El locale español asigna `nation.short.0=Neutral` y `nation.short.30=Amakna`.

Esto acredita la neutralidad del campo serializado actual de selección. No acredita el binding concreto de la tarjeta ni el paquete recibido por la sesión de la captura anterior. Tampoco cierra pasaporte, ciudadanía o territorios. Queda cotejar la selección recién cargada y los carriers de esas otras superficies; no se requiere modificar el cliente.


## Cotejo de bootstrap y modelo del pasaporte — 6 de octubre

El recorrido de selección `replay(45,114,...,character)` y login aplica `social.adapt` y `wire.adapt`. Roster propio, entidades13713/12666 y compañía13873 sustituyen la nación capturada por0. La sincronización15984 conserva regiones y limpia únicamente records nacionales formato17. Los fixtures antiguos muestran30, pero eso no acredita que el bootstrap actual conserve Amakna.

En el JAR, `ddU/cMC` gestionan apertura/categoría; el modelo `bVX` alimenta `nationId`, `isLocalNation` y `flagIconUrl` desde su record`luQ`. No se encontró en los carriers inspeccionados otra escritura de nación30. El log JSONL actual solo contiene opcode/tamaño, por lo que falta el cotejo de cuerpo real o lectura visual del pasaporte tras nuevo login. No atribuir una captura antigua a regresión actual ni declarar neutralidad visual sin comprobarla.


## Binding concreto corregido y prueba preparada

El descriptor nativo registra el comando `passport` con `PassportCommand`. Su frame `ddU` enlaza **`pvpLadderEntry` mediante `bMO.a(personaje,false)`**. El modelo obtiene la nación de `fri.fqe().Xt()` y expone `nationId` mediante `fxl.Xt()`. La aserción correcta dentro de `passportDialog` es `pvpLadderEntry.nationId == 0`. La referencia previa a `bVX.luQ` no demuestra el pasaporte: sus callsites corresponden a otros widgets nacionales/protectores, no al modelo enlazado por `ddU`.

Prueba nativa preparada: entrar con personaje de auditoría, ejecutar `/passport` en consola de comandos, comprobar ventana/modelo y texto nacional, cerrar con Escape, reentrar y repetir. Correlacionar con nación0 del actor en23548/12666/13713. `PASSEPORT_INFO` es una sección independiente y no sustituye esa aserción. Esta ruta fue cotejada en código nativo; aún no se ha ejecutado la aceptación visual.

## Revisión estática y log local — 7 de octubre

La lectura del serializador confirma que el valor que alimenta `bMO.nationId` proviene de la nación del personaje activo (`fri.fqe().Xt()` → `fxl.Xt()`), y el `wire.minimal_entity()` actual fija a `0` las secciones `NATION_ID` y `CHARACTER_LIST_NATION_ID` para las plantillas reconocidas. La prueba aislada previa verificó que el parser `qZ.aG` obtiene `0`; la localización asocia `nation.short.0` a “Neutral”. La captura visual antigua de Amakna no demuestra el comportamiento de la versión actual.

El log local de selección contiene envíos `15984`, pero registra solo opcode y tamaño; no contiene el cuerpo, por lo que no acredita en vivo los bytes nacionales. Sigue pendiente ejecutar `/passport` con un personaje actual y observar `passportDialog.pvpLadderEntry.nationId == 0` y el texto Neutral tras reconectar. Se dejó preparada la secuencia en [PRUEBA-GENERAL.md](PRUEBA-GENERAL.md).

La neutralidad del pasaporte/personaje está separada de la propiedad territorial: `territory_cells` conserva únicamente la correspondencia mapa/celda/región, y la adaptación de `15984` vacía solo el subtipo nacional formato17. No se encontró en esos datos una nación territorial autorizada para borrar o cambiar; esa parte sigue abierta hasta identificar un carrier/autoridad nativos específicos.

## Corrección de serializer y alcance territorial — 7 de octubre

La referencia a un item no era necesaria para investigar: `PassportCommand` activa `ddU`, `ddU` abre `passportDialog` y enlaza `pvpLadderEntry` a `bMO.a(personaje,false)`. El modelo nacional obtiene `nationId` de `personaje.fqe().Xt()`; por eso el carrier decisivo es `NATION_ID`, no un objeto del inventario. El parser qZ y el locale acreditan que `0` se representa como “Neutral”. La ficha antigua que mostró Amakna corresponde a una observación anterior, no a una captura actual del cuerpo del paquete.

La inspección de los layouts también encontró una sección independiente `PASSEPORT_INFO` (clase `rr`, longitud 1). Aunque el default del catálogo es `00`, `wire.minimal_entity()` no la reemplazaba: podía dejar pasar ese byte desde la plantilla. Se añadió `PASSEPORT_INFO` a `EMPTY_SECTIONS`; el serializer ahora sustituye esa sección por `ENTITY_DEFAULTS["PASSEPORT_INFO"]` y la prueba `test_passport_info_is_reset_with_character_nation` verifica que reemplaza `7f` por `00` sin alterar los bytes vecinos. El gate dirigido actualizado `test_wire test_social` pasó **39/39** con el entorno de verificación local. Aún falta confirmar en cliente el texto visible de `/passport` después de entrar y reconectar.

Para la petición territorial revisé los puntos de entrada y catálogos actuales: `territory_cells` resuelve map/cell a region para contexto ecológico, no a nation; no aparece en esos catálogos un campo de nación propietaria. La rama de `15984` reconoce registros públicos de nación formato17 y los sustituye por el constructor neutral vacío para el mismo ID, dejando intactos otros formatos. Eso es sincronización del estado público nacional, no una asignación/neutralización demostrada de los lugares. No se cambió esa semántica sin un carrier y consumidor nativo verificables; ownership territorial permanece pendiente.
