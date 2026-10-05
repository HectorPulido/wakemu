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
