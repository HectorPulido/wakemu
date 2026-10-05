# Auditoría de rendimiento del servidor Wakemu

Fecha: 4 de octubre de 2026. Complemento del ítem 0 de la auditoría general. **Solo propuestas para el servidor; ninguna corrección aplicada.**

## Alcance, método y límites

Se inspeccionaron rutas de solicitudes, movimiento, combate, persistencia y diagnóstico. Se analizaron los registros disponibles y se ejecutaron procesos Python aislados dentro del contenedor de mundo, con geometría real y actores sintéticos. No se reinició ningún servicio, no se modificó código ni configuración y no se alteraron grupos o combates existentes. El repositorio contiene cambios concurrentes: las pruebas aisladas usan los archivos actuales, mientras que registros históricos pueden corresponder a otras versiones cargadas.

Las cifras son muestras diagnósticas, no percentiles de una prueba de carga. Las latencias presentadas son ejecuciones sin profiler; `cProfile` se utilizó únicamente para atribuir coste. No se suma tiempo de diferentes pruebas para afirmar una latencia total real. Artefactos privados: `.runtime/local/instances/audit-20261004/performance-isolated-fixture.py` y `performance-isolated-fixture.txt`.

Se creó el personaje nuevo **Audit Tempo**, ID 10, con perfil independiente. El ensayo gráfico quedó interrumpido por paro programado: el cliente registró la desconexión a las 07:15:08.700 UTC, antes del clic de las 07:15:15.810 UTC. Este intento no mide latencia de un hechizo ni demuestra un bloqueo causado por el clic. El cliente se utilizó solo como instrumento; sus modificaciones quedan fuera del alcance solicitado.

## 1. Movimiento de monstruos: coste por grupo y bloqueo compartido

En `maps/monster_wander.py::plan`, cada grupo cercano convierte las aristas del mapa en un conjunto y recorre el conjunto completo para encontrar salidas del líder. En el mapa 1134 son **37.157 celdas y 125.989 aristas**. Además, `wander_location` vuelve a construir ocupación de otros grupos dentro del bucle.

| Prueba aislada | Tiempo observado |
| --- | --- |
| Plan de un grupo | 123–147 ms |
| Simulación de 8 grupos | 1.069 ms |
| Simulación de 16 grupos | 1.936 ms |
| Simulación de 32 grupos | 3.835 ms |

Estas pruebas usaron un registro en memoria y publicación vacía; **excluyen Redis y sockets**. Los grupos estaban cerca del jugador. No debe extrapolarse el resultado a todos los grupos persistidos: los lejanos pueden salir antes del recorrido costoso.

`local_game_server.py::wander_monsters` mantiene `COMBAT_GROUPS.lock` y `HARVESTS.lock` durante el recorrido de zonas, cálculo, actualización y publicación. El inicio de combate también necesita el bloqueo de grupos. La espera por este bloqueo es una causa plausible de latencia irregular; falta medir su duración en el proceso vivo. Los hilos también compiten por CPU del intérprete.

**Propuesta:** cachear un índice de adyacencias por origen y geometría inmutable; mantener ocupación por zona; obtener snapshot/versiones bajo bloqueo, calcular fuera y aplicar únicamente si no cambiaron estado, posición, combate o recolección. Publicar después de liberar el bloqueo, preservando orden y versión. No mover un grupo que acaba de entrar en combate.

La política solicitada —zonas con jugadores, evaluación cada 5 segundos, 25% de probabilidad y cantidad aleatoria de pasos válidos— reduciría actividad y sincronía, pero no elimina el coste estructural. El worker ya limita ubicaciones a mapas/instancias con jugadores; eso no demuestra que crecimiento y reproducción cumplan la misma política.

## 2. Combate: geometría copiada en cada transacción

`combat_spell_transaction.py::prepare_spell_transaction` crea un snapshot completo y hace `deepcopy(fight)`. `combat_spell_commit.py` vuelve a comparar snapshots completos antes y después de serializar estadísticas. La geometría forma parte del estado copiado, aunque el hechizo no la modifique.

La prueba utilizó dos actores sintéticos y el hechizo 5038, con catálogos precargados, la misma posición y dos tamaños de arena:

| Medida | Radio 12 | Radio 89 |
| --- | --- | --- |
| Celdas / aristas | 465 / 1.634 | 7.075 / 24.556 |
| Snapshot serializado | 92.796 bytes | 844.397 bytes |
| Snapshot individual | 3,7 ms | 60,6 ms |
| Copia profunda individual | 5,2 ms | 86,9 ms |
| Preparación caliente | 13,1 ms | 155,7 ms |
| Confirmación | 7,9 ms | 143,0 ms |

Preparación más confirmación pasa de unos **21 a 299 ms**. La confirmación utilizó un serializador de estadísticas vacío: es un coste parcial, sin persistencia ni red. La primera preparación en radio 12 tardó 223 ms, frente a 13 ms en la siguiente, señal de trabajo de primera utilización. La precarga previa tardó 9,11 s, pero ocurre antes de aceptar conexiones y no explica por sí sola retrasos repetidos en sesión.

En el perfil de radio 89, copia profunda y snapshot absorbieron aproximadamente el 97% del tiempo de preparación. Las medidas anteriores no contienen el sobrecoste del profiler. Los checkpoints reales consultados, con dos actores, contenían estados de aproximadamente 632–712 KB y hasta 26.120 aristas: los estados grandes no son exclusivos de la prueba sintética.

**Propuesta:** separar geometría inmutable compartida del estado mutable; conservar snapshot transaccional de actores, recursos, efectos y secuencia; sustituir comparaciones completas por una versión autoritativa validada antes de confirmar. Mantener las garantías contra transacciones obsoletas y callbacks que mutan estado. Reducir el radio arbitrariamente podría alterar accesibilidad y jugabilidad; la comparación identifica el coste, no prescribe ese cambio.

## 3. Construcción de arena y checkpoints

`combat_arena_selection.py::bounded_arena` valida la geometría completa antes del recorte. Cachear el JSON en `combat_terrain.py` no evita esa validación por combate. En ejecuciones aisladas, construir arena costó **305–346 ms con radio 12** y **417–491 ms con radio 89**. Incluso una arena pequeña conserva gran parte del coste fijo.

**Propuesta:** validar e indexar cada versión del mapa una vez; seleccionar y validar el recorte sin recorrer de nuevo todas las aristas. La clave de caché debe incluir versión de geometría y restricciones dinámicas pertinentes.

`local_game_server.py::checkpoint_fight` guarda snapshots completos síncronamente; el cierre normal del dispatcher lo llama cuando existe combate. Algunas rutas también lo llaman explícitamente. Se debe comprobar cuántos guardados hace cada solicitud y cuáles corresponden a cambios reales. El coste de copia, JSON y escritura puede retrasar la lectura de la siguiente solicitud aunque parte de los paquetes ya se haya enviado.

**Propuesta:** evitar checkpoints idénticos y duplicados; diseñar journal de cambios o escritor ordenado por combate con barreras de durabilidad y control de revisión. No convertir la persistencia en un simple proceso asíncrono sin garantías: validar caída entre confirmación, guardado y respuesta, recuperación y prevención de doble recompensa.

## 4. Envíos bajo bloqueo global y esperas externas

`maps/world.py` envía a peers desde operaciones protegidas por `WORLD.lock`. La adquisición del bloqueo de escritura del peer y la escritura de socket pueden retener ese bloqueo global. Un receptor lento podría retrasar a otros jugadores. Es una **hipótesis estructural, todavía sin reproducción de receptor lento**.

**Propuesta:** recoger destinatarios bajo bloqueo y usar colas de salida acotadas por conexión, con orden de mensajes, manejo de desconexión y política explícita para saturación. Medir espera de lock y tiempo de socket por peer antes de cambiar el diseño.

SQLite tiene un límite de espera de 10 s; Redis, de 2 s por operación. Estos límites hacen posibles esperas acumuladas, pero no demuestran que hayan ocurrido. Las lecturas aisladas fueron rápidas y no evalúan contención de escritura. La IA tiene timeout HTTP de 1 s por petición; medir peticiones secuenciales por turno y su preparación antes de atribuirle el retraso total.

## 5. Lo que demuestran los registros y lo que falta

Se encontraron 123 solicitudes completas con la instrumentación disponible. Diez lanzamientos recientes de Sacrógrito mostraron aproximadamente **374–4.037 ms** desde recepción hasta registro de lanzamiento; no cubren necesariamente el checkpoint posterior. La entrada al mundo alcanzó **7.770 ms**, con un intervalo grande antes del contexto ecológico. Una carga aislada actual del contexto ecológico tardó solo unos 88 ms: no demuestra la causa de ese intervalo histórico.

Los cuatro inicios de combate medidos por solicitud tardaron 347–558 ms, pero fueron **rechazos de validación**, no inicios exitosos. No sirven como referencia del combate completo. No apareció una reproducción concluyente de los 20 s reportados.

`RequestTrace` empieza después de recibir el paquete completo. El bucle puede hacer tareas de sesión antes de leerlo. Además, `finish` calcula `elapsed_ms` antes del snapshot final y del flush de registros. Por ello, una solicitud aparentemente rápida puede coexistir con espera previa o trabajo posterior no incluido.

**Instrumentación propuesta, únicamente del servidor:** tiempo de entrada en el bucle y lectura de frame; tareas previas; espera y posesión de locks; selección de arena; preparación, estadísticas y confirmación; checkpoint/codificación/escritura; cola de salida y envío; emisión y recepción del ACK de acción. Correlacionar conexión, solicitud, combate, acción y boot del proceso usando reloj monotónico para duraciones. No registrar credenciales ni payloads privados.

## 6. Contexto nuevo: Redis primero y persistencia a los 20 minutos

El requisito añadido al punto 0 exige reducir consultas SQL, con lectura Redis primero y flush posterior, preservando objetos. La implementación actual es un journal parcial: `Store.character` arma el estado desde SQL antes de aplicar el overlay Redis de builds. No es una caché integral del personaje.

Se ejecutó `review-context/sql-redis-probe.py` sobre SQLite temporal y MemoryRedis, con `set_trace_callback`. Conteos de statements, no viajes de red ni filas modificadas:

| Operación | SELECT | INSERT emitidos | UPDATE | CREATE IF NOT EXISTS |
| --- | ---: | ---: | ---: | ---: |
| Cargar personaje sin registro Redis | 8 | 3 | 0 | 7 |
| Guardar build con Redis | 20 | 6 | 2 | 15 |
| Cargar personaje con hit Redis (3 repeticiones iguales) | 9 | 3 | 0 | 7 |
| Flush antes de 1.200 s | 0 | 0 | 0 | 0 |
| Flush al alcanzar 1.200 s | 3 | 1 | 0 | 0 |

Los INSERT de carga inicializan datos con operaciones idempotentes; no significan objetos nuevos en cada lectura. Los hit conservaron una lectura de `character_builds` SQL. La hoja no estaba en SQLite antes del plazo y apareció al cumplirse; salud/lease no siguen ese plazo. El guardado inicial tardó 223 ms con primera utilización de catálogos; las cargas hit fueron 0,70–0,86 ms. Estas cifras no representan Redis real ni concurrencia y no explican por sí solas el pico de 20 s.

**Propuesta:** cachear catálogos y snapshots versionados por dominio; usar miss real para hidratar SQL y reutilizar estado dentro de la solicitud. Mover creación de schema/datos iniciales a migraciones. Conservar autoridad de propiedad/lease y durabilidad antes del ACK. Para transferencias de objetos no basta cachear cada personaje por separado: consumo y entrega, UID, cantidades y recibo de operación requieren una transición atómica con revisión para impedir doble aplicación.

Redis caído no equivale a clave ausente: consultar SQL antiguo mientras existen mutaciones sin flush puede duplicar un objeto ya consumido. `StateJournal` evita ese fallback silencioso. La propuesta debe mantenerlo, usar CAS, baseline comprobado y limpieza condicionada a la revisión confirmada. La recuperación tras commit SQL y antes de limpiar Redis debe reconocer lo ya aplicado; una actualización concurrente debe permanecer pendiente.

Cron declara builds/grupos a 1.200 s y posiciones a 2 s; Compose declara AOF `appendfsync always`. No se verificó aquí el fsync efectivo de Redis cargado ni la recuperación tras caída del host. Se reejecutó la suite de builds/journal junto con elementos: 23 descubiertos, **13 ejecutados OK y 10 omitidos** por requerir Redis real. Los resultados previos con Redis real siguen separados, no se cuentan como una nueva ejecución. Artefactos privados: `.runtime/local/instances/audit-20261004/review-context/sql-redis-probe.py` y `sql-redis-results.json`.

## Prioridad y criterios de aceptación

1. Medir fases y bloqueos para localizar la cola que explica los picos; identificar la versión cargada del servidor.
2. Indexar movimiento y reducir duración de bloqueos, preservando exclusión combate/recolección.
3. Sacar geometría inmutable de las copias transaccionales y cachear validación de mapa.
4. Eliminar guardados redundantes con una política de recuperación explícita; aislar sockets lentos.

Comparar p50/p95/p99 y máximos con 1, 16 y 32 grupos cercanos, varios jugadores/combates, primer hechizo y hechizos calientes, escritura concurrente y receptor lento. Verificar además que no haya movimiento durante combate, acciones duplicadas, desorden de ACK, pérdida de persistencia ni recompensas dobles. Definir el objetivo de latencia con esas medidas; una muestra aislada no acredita un SLA.
