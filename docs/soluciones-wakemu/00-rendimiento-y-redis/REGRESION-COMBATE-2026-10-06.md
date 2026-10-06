# Regresión de ataque y desconexión del 6 de octubre

## Reproducción y límite de autorización

Audiluna, Yopuka nivel100, build predeterminada, pelea contra Tofu de nivel8. El usuario intentó el puño y después un hechizo; el puño fue rechazado y el hechizo desconectó. El usuario confirmó que antes funcionaban y pidió explícitamente preservar el trabajo de la sesión de hechizos. Esta investigación no modifica ese motor ni aplica un rollback.

## Puño: fallo de contexto de efecto

A05:41:33 UTC llega12889, UID de arma−1 y slot15. El servidor registra `combat_melee_rejected`: `Missing actual triggering eVo.aZY`, `UnknownCondition`. Cadena158454→3597→398721; la condición falla dentro del efecto398721. El checkpoint se guarda, pero el ataque no se confirma. La recepción del comando está acreditada; no corresponde a un botón sin handler.

## Hechizo: fallo de alcance del serializador

A05:41:37 UTC llega13260. El commit intenta invocar `current_combat_stats` desde una lambda del dispatcher y lanza `NameError`. La función está definida dentro de `apply_readiness`, mientras esa lambda está en el alcance de `session`; Python no puede resolverla allí. El log registra `unexpected_request_exception` y después cleanup/desconexión. Fight3, actor1, objetivo−3538964118812759088, mapa1134.

## Comparación sin alterar el árbol

La imagen previa `33a78a4819e2b791eade0c67e02193a693de8545d51d649a4bfa7651dfae1f7f` también contiene esa definición anidada y llamadas externas. El AST de esa imagen sitúa la definición en928 y las llamadas en2026/2168/2245; el archivo actual las sitúa en938 y2058/2200/2277. Esto acredita que el defecto de alcance ya aparece en ese artefacto, pero no demuestra que el proceso anterior lo hubiera cargado ni descarta la regresión observada tras recargar el árbol compartido. Hay lanzamientos exitosos anteriores en el log del5 de octubre; no se considera estable el combate actual por los gates de builds.

## Trabajo requerido por la sesión responsable

Revisar la disponibilidad del serializador en todas las rutas de commit sin cambiar su semántica, y cotejar el contexto real de disparo de398721 en el puño. Probar ambos ataques en la versión exacta que se desplegará y verificar ausencia de desconexión y atomicidad de AP/HP/estados. No silenciar la condición, inventar `eVo.aZY`, eliminar efectos ni revertir el motor a una versión antigua como atajo.

## Cotejo del snapshot funcional y corrección acotada

El snapshot `.runtime/local/instances/audit-builds-server-20261004/snapshot/local_game_server.py` define `current_combat_stats` dentro de `session` (línea 1672). El código actual lo había situado dentro de `apply_readiness`. El bytecode confirma que los callbacks externos intentaban resolverlo como global. Esto aporta una comparación concreta del alcance anterior y actual, además de la traza del fallo.

Se movió exclusivamente el mismo serializador al alcance de sesión, con sus imports propios. No se cambiaron reglas, efectos, decks ni el motor de hechizos. Corrección pendiente de validación y recarga del servidor; no se declara resuelto el combate. El fallo independiente de contexto `eVo.aZY` sigue pendiente.

## Estado residual reportado

El usuario aportó una captura posterior con el personaje en el mundo pero la barra de acciones todavía con apariencia de combate. Debe cotejarse el cierre nativo de la pelea y el bootstrap de reconexión; guardar heridas y liberar la pelea en el servidor no prueba que el cliente haya recibido el cierre correcto. Pendiente de reproducción y comprobación de paquetes.

## Validación y despliegue del alcance

Gate aislado PostgreSQL/Redis: 45 pruebas OK (`test_combat_spell_transaction`, `test_combat_melee`, `test_combat_geometry_snapshot`, `test_session_cleanup`, `test_placement_deadline`, `test_combat_group_target`). El harness de colocación incluye ahora el helper de sesión y una regresión comprueba que los tres callbacks lo capturan con `LOAD_DEREF`. Dos fallos adicionales del módulo weapon ya constaban en corridas anteriores y no se alteraron para hacer pasar el gate.

Se reinició únicamente `world` para cargar el archivo montado corregido. Prueba visual de ataque pendiente; no se declara cerrado el incidente ni el fallo independiente del puño.

## Cotejo de la reconexión residual

El cierre por excepción guardó HP y abortó el checkpoint a 05:41:38 UTC. A 05:42:25 hubo nuevo bootstrap de mundo, sin bootstrap de pelea; no hubo callback 12925 entre el fallo y esa reconexión. `join_world` publica el estado de exploración, pero no reconcilia el combate visual interrumpido. Esto explica una divergencia compatible con la captura, aunque queda por verificar el cierre nativo exacto.

12925 es una petición del cliente tras su limpieza `aUH`, no un mensaje que el servidor pueda enviar para forzarla. Investigar reconciliación explícita de combate interrumpido al reconectar y cotejar el consumidor de resultado12238; no inventar victoria, recompensas ni enviar un callback de cliente como paquete de servidor. La corrección de alcance recién cargada previene ese NameError; no demuestra por sí sola que la reconexión residual esté resuelta.

### Corrección del candidato de limpieza

El cotejo completo de `aUH.cXi` contradice la recomendación de usar huN=true como limpieza neutral: en 1v1, retirar al jugador deja menos equipos que fUM y retorna antes del teardown visual, aunque pueda emitir12925. Se corrigió la anotación desactualizada del catálogo de auditoría. No se implementó ese candidato. Se mantiene pendiente un protocolo de reconciliación acreditado.

## Contexto del puño localizado, sin modificar el motor

El plan de `combat_melee.py` declara un contenedor real `type=12,id=2145,is_spell=false`. La cadena de eventos conserva ese descriptor al construir `NativeEventSource`. Sin embargo, `condition_identifiers` transmite el discriminador al contexto de condición solo para tipos1,3,11,25: omite12. Es una brecha candidata del adaptador de contexto, no una razón para alterar398721 ni introducir un trigger artificial en158454.

Falta acreditar con productor/consumidor nativo que type12 corresponde a eVo.aZY del item, y luego probar daño→evento→replay→condición y la transacción completa, conservando el rechazo de discriminadores desconocidos. No se modificaron archivos del motor.

## Aceptación manual posterior a la corrección de alcance

Usuario confirma dos ciclos completos: Fulgor4775 en pelea4 y Super Puño Iop4777 en pelea5; ambos aplican daño, terminan y retornan al mundo sin desconexión ni interfaz residual. Logs06:11:08 y06:11:58 UTC registran `combat_cast` y `combat_finished`, seguidos de12925. Se confirma recuperado ese recorrido; no se cierra rendimiento ni interrupciones inesperadas. La primera entrada tardó más que la segunda. Listo→activo en pelea4:169ms; en pelea6:115ms. Esto mide el handler, no toda la latencia visual.

El usuario confirma que el ataque básico sigue rechazado. El bytecode `fnR.aZY()` retorna literalmente12; se restauró su transmisión en `condition_identifiers`. Cambio acotado al adaptador de contexto, sin alterar efectos ni fórmula. Prueba de cadena completa y despliegue pendientes.

## Demora inicial medida

Request13130 `a1913c6a489d49c887ebd22ab34f48f8`: 18.205,96ms totales; `combat_forced_terrain_ready` acredita17.709,695ms de `prewarm_map` (mapa actual del personaje), antes de publicar colocación. La segunda y tercera entrada registran397,326 y399,519ms. Por tanto la principal diferencia observada es la carga fría/validación de `compact_index`, no el handler de Listo ni una espera atribuida sin evidencia a PostgreSQL. La preparación cacheada cambia la latencia, sin certificar aún todos los mapas.

Revisar carga y representación del catálogo conservando sus máscaras de altura y transiciones nativas; no suprimir la validación ni inventar terreno. No se modificó ese módulo durante esta revisión.

### Contraste aislado de la carga fría

El mapa medido es337. El mismo módulo y catálogo copiados a un proceso Docker aislado cargan en184ms y repiten en0,186ms: los17,7s del proceso activo no se explican por el tamaño normal de ese archivo. Queda por cotejar contención CPU/memoria y bytes exactos usados durante el pico. No se atribuye el retraso íntegro al costo intrínseco de JSON.

Existe otro problema de escala: mapa235 ocupa644.324 filas y el benchmark eleva RSS de10,51 a571,84MiB, con carga fría2,43s. `transitions` conserva referencias de `HeightPolicy` a índices que `compact_index` puede haber expulsado; su LRU de cuatro entradas no limita por sí sola todos los índices retenidos. Revisar propiedad única de la caché y una representación compacta con procedencia y máscaras exactas. Ninguna caché del servidor activo fue alterada para medir.
