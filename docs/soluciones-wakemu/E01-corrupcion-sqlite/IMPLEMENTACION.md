# Migración PostgreSQL en curso

E01 tiene prioridad de implementación antes de continuar otros sistemas persistentes. Sin compatibilidad SQLite, doble backend ni traductor de SQL.

## Verificación actual del Docker local

El entorno autorizado es el Compose local `wakfu-local`. Verificado el 5 de octubre: `world` y `postgres` saludables. El proceso de juego sigue usando el código SQLite que cargó antes de la adaptación de Store; no reiniciarlo hasta completar los consumidores PostgreSQL necesarios.

Store ya utiliza el pool PostgreSQL para cuentas, autenticación, tokens y leases. La consumición de un token usa un único `DELETE ... RETURNING`; el reemplazo de sesión bloquea la cuenta y la limpieza exige la generación correspondiente.

Validación repetida contra `wakemu_migration_test`: `test_postgres_store_auth`, 4 pruebas PASS. Incluyen dos conexiones concurrentes consumiendo el mismo ticket (solo una lo obtiene), autenticación y rechazo de duplicados, reemplazo de lease, limpieza de una generación antigua y caducidad. No acreditan todavía login completo ni persistencia de personajes.

La clase Store sigue parcialmente portada: desde creación de personaje hay consultas SQLite pendientes. El código montado no es apto para reiniciar el servidor como PostgreSQL todavía. Próximo paso: personajes, hidratación de dominios y operaciones de inventario/builds, manteniendo transacciones y propiedad verificadas.

## Estado ejecutado

Servicio `postgres` en Compose, PostgreSQL17, volumen persistente en red interna sin puerto publicado; contraseña en archivo privado. `SHOW default_transaction_read_only` devuelve `off`.

Migraciones001 y002 ejecutadas transaccionalmente con `psql ON_ERROR_STOP`: cuentas, personajes, sesiones, tokens, auditoría administrativa, inventario y reservas. IDs bigint, timestamps UTC, flags boolean, documentos jsonb y blobs bytea. Secuencia compartida de UIDs en sustitución de `inventory_uid_sequence`; no se preserva el esquema anterior.

Prueba `server/tests/postgres_inventory_constraints.sql` ejecutada contra PostgreSQL real: PASS para secuencia compartida, FK de propietario de contenedor, FK de personaje seleccionado, slot único y máscara de elementos. Los datos de prueba se revierten. No acredita todavía concurrencia ni todas las operaciones de inventario.

## Pendientes obligatorios

- Inventario actual del código:29 tablas declaradas; la auditoría original de27 precedía roles y selección de build. Recontar al terminar el nuevo esquema.
- Completar migraciones de todos los dominios y runner con checksum/versionado; las ejecuciones manuales iniciales aún no están registradas en `schema_migrations`.
- Incorporar driver/pool PostgreSQL y portar consultas, transacciones, tipos y excepciones; retirar DDL durante cargas y llamadas a schema.
- Portar journals y definir autoridad conjunta de hojas/selección para E07.
- Pruebas de concurrencia, rollback, recuperación y restauración contra PostgreSQL.
- Cambiar configuración de world y verificar login/cliente antes del cierre.

El servidor de juego todavía usa SQLite. Tener PostgreSQL levantado y ejecutar parte del esquema no constituye cutover. Los cambios están en el checkout local, sin commit/push.

## Dominios de personaje

Migración003 ejecutada contra PostgreSQL: parámetros jsonb, hojas bytea, selección/revisión, XP, wallet único por cuenta, regeneración con timestamps UTC, oficios, tutoriales boolean, transportes y merkasaco jsonb. No existe saldo duplicado de kamas por personaje en el contrato nuevo. El estado PostgreSQL tiene21 tablas incluyendo `schema_migrations`; combate, ecosistema y adaptación de consumidores siguen pendientes.

Añadida dependencia `psycopg[binary,pool]==3.2.10` al build; aún no se declara instalado/cargado en world ni reemplazado Store. Runner y pruebas de los nuevos consumidores son el siguiente paso.

## Pool y migraciones versionadas

Implementado `storage/postgres.py`: pool con conexiones por transacción, filas dict, contraseña desde archivo privado; sin adaptación SQL SQLite. Runner `tools/migrate_postgres.py`: secuencia contigua de versiones, SHA256, lock transaccional entre procesos y aplicación atómica. `schema_migrations` pertenece al runner, no a001.

Base nueva `wakemu_migration_test`: runner aplicó3 migraciones; segunda ejecución0. Dos pruebas reales en schemas aislados PASS: cambio de checksum rechaza y conserva historial; migración fallida después de CREATE TABLE revierte tabla y versión. Driver preparado temporalmente en `/data/migration-driver` para estas pruebas; el Dockerfile incluye ahora migraciones y CLI para el build definitivo. No se sustituyó todavía Store ni se recargó world como PostgreSQL.

## Combate y ecosistema

Migración004 aplicada mediante runner: combate durable con ID identity signed32, participantes con propiedad verificada, recibos únicos por combate/personaje (generación queda como dato, no como parte de la clave), salud de salida, checkpoints jsonb, grupos/claims de NPC, plantación/outboxes y recibos de extracción con ámbito mapa/instancia.

Esquema nuevo:32 tablas. Respecto de las29 originales se retira `inventory_uid_sequence`, se incorpora `schema_migrations` y se agregan combate durable, participantes y claims de NPC. No importar IDs aleatorios de combates como si fueran el asignador definitivo; el runtime debe pedir la nueva identidad a PostgreSQL. No implementar FK desde recibos/outbox al ítem o recurso vivo que puede desaparecer.

Tres pruebas PostgreSQL PASS: runner/checksum, rollback de migración y restricciones durables. Recompensa repetida con generación distinta rechaza por PK; mismo NPC en dos grupos de una instancia rechaza por PK. Son pruebas de restricciones, no todavía carreras concurrentes ni integración con dispatcher/journals. Portar consumidores y comprobar el ciclo real siguen pendientes.

La limpieza de selección (`clear_character`) también usa PostgreSQL y timestamps UTC. Prueba adicional PASS: una generación sustituida o caducada no puede limpiar la selección; la vigente sí, sin cerrar la sesión.

## Asignador y reservas de inventario

Retirado el DDL y contador SQLite de `inventory_uids`: `allocate` usa `nextval('inventory_uid')`, compartido con los defaults de bolsas e ítems. Las reservas bloquean la sesión vigente antes de contar el cupo, evitando que dos peticiones superen conjuntamente127 UIDs pendientes. La validación verifica personaje seleccionado y expiración UTC sin depender de la hidratación aún pendiente.

Seis pruebas PostgreSQL PASS en `test_postgres_store_auth`: además de las cuatro anteriores, cuatro conexiones asignan128 IDs distintos; un ID consumido en una transacción revertida no se reutiliza. Dos peticiones simultáneas de80 reservas producen una aceptación y un rechazo, con80 filas persistidas. La transferencia nativa y los demás consumidores de inventario siguen pendientes de port; esto no acredita el ciclo de split del cliente.

## Contenedores iniciales

`inventory.initialize` ahora es una operación explícita bajo lock de personaje: registra la inicialización y crea bolsillo30/bolsa4 en la misma transacción usando el default de la secuencia compartida. `load` solo consulta; no crea tablas ni inventarios durante lecturas. El encoder exige contenedores persistidos y valida el bolsillo base sin suponer un UID derivado del ID del personaje.

Séptima prueba PostgreSQL PASS: rollback no deja marcador ni bolsas; dos inicializaciones concurrentes producen exactamente los mismos dos contenedores y UIDs distintos. También verifica el encabezado de dos bolsas del encoder nativo. La creación de personaje debe integrar esta inicialización antes de su primera hidratación; aún pendiente, junto con los demás dominios de esa lectura.

## Ítems y selecciones elementales

Lectura de ítems y persistencia/copia/hidratación de máscaras usan PostgreSQL; retirado el DDL de estos módulos. Hidratación usa `uid = ANY(%s)` y mantiene ausentes las opciones no asignadas. El lease de inventario bloquea sesión y personaje propios; grants usan ese lock para serializar ocupación del slot antes del INSERT.

Nueve pruebas PostgreSQL PASS. Las dos nuevas comprueban persistencia de máscaras10/20 y copia sin reroll entre conexiones, ausencia de opciones preservada, y dos grants simultáneos al mismo slot: exactamente uno aceptado y una fila persistida. La eliminación aún requiere la hidratación completa de Store y transferencia/bolsas siguen pendientes; no se declara ciclo de inventario completo.

## Creación e hidratación de personajes

Store crea personaje, salud nativa inicial, contenedores, progresión, wallet, merkasaco y selección de build en una sola transacción PostgreSQL. Bloquea la cuenta antes de comprobar capacidad; nombre canónico único y RETURNING sustituyen el comportamiento SQLite. JSONB se adapta con Jsonb y se lee como documentos; la capacidad de builds se valida como entero JSON. XP y kamas se leen de sus autoridades, sin reparar ni crear filas durante la lectura. Se eliminaron las reparaciones de formatos históricos en la lectura de merkasaco.

Once pruebas PostgreSQL PASS: creación con todos los dominios iniciales y lectura idéntica desde otra conexión; duplicado de nombre con distinto case rechaza sin dejar otro personaje; dos creaciones simultáneas con capacidad1 dejan exactamente un personaje. Aún faltan selección/movimiento, mutaciones de otros dominios, journals y cutover. Estas pruebas usan Store real, no sustituyen el login nativo ni acreditan la migración completa.

## Selección y movimiento

Store usa un orden de locks consistente (sesión vigente, después personaje propio) para selección y movimiento. El movimiento valida enteros y rangos de wire antes del SQL, coteja origen bajo lock y guarda destino con propietario explícito. Selección rechaza personaje ajeno y generación sustituida sin modificar el lease vigente.

Doce pruebas PostgreSQL PASS. Nueva prueba con personaje creado mediante Store: selección, dos movimientos concurrentes desde el mismo origen (solo uno aceptado), persistencia del destino y rechazo de selección/movimiento desde la generación reemplazada. Aún no acredita movimiento nativo en el cliente, flush diferido ni recuperación de journals.

## Transferencias y bolsas

Consultas de `inventory_move` e `inventory_bags` portadas a PostgreSQL, con transacciones del pool y lease/personaje bloqueados. Acceso a filas de slots usa dict_row; no hay BEGIN IMMEDIATE. Reservas de split mantienen el recibo bytea para repetición idempotente.

Catorce pruebas PostgreSQL PASS. Split nativo12804 de5 unidades produce3+2; repetir el mismo body no aplica otra vez; cambiar el body con el mismo UID rechaza; fusionar vuelve a5. Equipar una bolsa apilada3 crea UID de contenedor independiente y deja2; retirarla devuelve1 con ese UID y conserva la pila2; lectura desde otra conexión confirma el estado. La prueba utiliza bolsa2603, no acredita todavía el Sadida12493 ni interacción GUI. Journals/builds/salud/combate y configuración de cutover siguen pendientes.

## Salud y regeneración

`health_store` usa timestamps UTC `started_at/last_at`, consultas PostgreSQL y el lock sesión/personaje para mutaciones. Se retiró su DDL de ejecución. Inicialización con conexión prestada exige transacción PostgreSQL activa y mantiene el commit/rollback del llamador. Tick conserva el cálculo nativo en milisegundos, lee XP y wallet de autoridades separadas y vuelve a validar bajo lock antes de persistir regeneración.

Quince pruebas PostgreSQL PASS. La nueva verifica inicialización, daño con HP esperado, rechazo de actualización obsoleta, regeneración, rechazo de reloj anterior y rollback de inicialización prestada sin alterar el HP confirmado. Aún faltan consumidores de salud en builds y combate; no acredita el ciclo de combate completo.

## Builds SQL

Guardar/activar/borrar builds usan PostgreSQL y el lock conjunto de sesión/personaje. Selección, revisión, HP/máximo y baseline de regeneración UTC se actualizan dentro de la misma transacción. El camino con journal todavía debe portarse; no se habilita borrado con journal hasta integrar selección y hojas bajo una autoridad conjunta.

Dieciséis pruebas PostgreSQL PASS. Nueva prueba: guardar build1, activar y releer selección/revisión desde otra conexión, rechazar borrado durante combate y borrar activo regresando a0 con revisión2, sin superar máximoHP. Esta cobertura corresponde al camino SQL; falta rollback inyectado, carreras de builds, journal y cliente nativo.

## Transición de mapa y wallet

Transición de mapa usa lock sesión/personaje, compara toda la ubicación de origen y guarda destino en PostgreSQL. Map ID respeta signed32 del esquema; instancia bigint. Registro de cuenta crea wallet en su misma transacción; consulta de saldo solo lee esa autoridad, sin sumar saldos históricos por personaje ni crear filas durante login.

Diecisiete pruebas PostgreSQL PASS. Nueva prueba verifica wallet antes de crear personaje, transición completa mapa/instancia/XYZ, rechazo de repetir origen obsoleto y mismo saldo123 visto por login y lectura de personaje. Store ya no contiene SQL SQLite; siguen pendientes consultas en journals y otros módulos. No equivale a cutover del proceso world.

## Autorización administrativa

`command_permissions` usa booleanos PostgreSQL, política de comandos JSONB y auditoría UTC. Retirado el DDL/ALTER/PRAGMA durante ejecución. Cambio de rol y registro de auditoría comparten transacción, y cada autorización consulta el rol actual.

Dieciocho pruebas PostgreSQL PASS. Nueva prueba: cuenta normal acepta!pos y rechaza!nivel; promoción permite!nivel; revocación vuelve a rechazarlo sin renovar sesión. Auditoría registra ambos cambios como booleanos con timestamps de zona horaria. Todavía debe verificarse el API/dispatcher completo después del cutover.

## Tutoriales, descubrimientos y niveles de oficio

Tres consumidores portados: tutoriales con pending boolean, descubrimientos con INSERT ON CONFLICT idempotente y niveles/aprendizaje de oficios. Se retiró DDL de ejecución y los cambios exigen leases PostgreSQL vigentes. El consumidor de plantación ya no solicita crear la tabla de oficios.

Diecinueve pruebas PostgreSQL PASS. Nueva prueba acredita tutorial pendiente/leído, descubrimiento persistido e idempotente, aprendizaje de oficio a0 y rechazo de descubrimiento con generación reemplazada. No implementa XP de oficio ni resuelve por sí misma sus issues de gameplay. La suite histórica todavía contiene fixtures SQLite y debe migrarse también; estas pruebas nuevas son las ejecutadas contra PostgreSQL real.

## Guardado del merkasaco

Mutación de configuración usa lock sesión/personaje y Jsonb para layout, acceso y muebles; locked es boolean. Retirado schema/PRAGMA/ALTER del módulo. La validación previa de estructura y referencias sigue vigente; esta migración no agrega nuevos flujos de inserción de gemas/muebles.

Veinte pruebas PostgreSQL PASS. Nueva prueba guarda bloqueo y documentos JSON, relee estado idéntico desde otra conexión y confirma que una generación sustituida no puede desbloquearlo. Aún falta probar las interacciones nativas de personalización y auditar todas sus reglas de propiedad; no se declara resuelto el issue de merkagemas.

## Checkpoints de combate

Snapshots JSONB y timestamps UTC; sin DDL de arranque. Save exige lease vigente, actor seleccionado controlado y participante durable PostgreSQL del mismo combate/cuenta/personaje; bloquea el combate antes de crear o comparar revisión. Read recibe documentos ya decodificados. End conserva CAS de revisión y estado active.

Veintiuna pruebas PostgreSQL PASS. Nueva prueba con combate durable y actor mínimo: revisiones1→2, rechazo de revisión antigua, snapshot de HP persistido, cierre a3 y rechazo de edición terminal. La primera ejecución falló solo al limpiar fixtures por FK; corregido el orden de limpieza y repetida la suite completa PASS. No acredita todavía snapshot de un combate nativo completo ni recuperación de todas las estructuras de efectos.

## Recompensas durables

Award usa locks de sesión/personaje, combate durable y wallet. Exige participante propio del equipo ganador y combate durable finished. Recibo único se consulta por combate/personaje sin generación; una sesión nueva no habilita otro premio. XP, wallet, nivel, salud dependiente y recibo se guardan en la misma transacción. Retirado el DDL y sumatorio de saldos históricos.

Veintidós pruebas PostgreSQL PASS. Dos awards concurrentes del mismo combate producen exactamente uno nuevo; después de reemplazar sesión el mismo combate no premia otra vez. Persisten XP1000/kamas10 una sola vez, subida de nivel y salud máxima coherente. Usa política explícita de prueba, no fórmula oficial ni loot. Lifecycle debe crear participantes durables y actualizar finished antes de llamar award; sigue pendiente su adaptación y prueba de combate nativo.

## Salud al salir del combate

Persistencia PostgreSQL con recibo único combate/personaje, propietario durable validado y baseline de regeneración UTC. Recibo y HP se guardan juntos; la generación no forma parte de la identidad idempotente. Retirado DDL de ejecución.

Veintitrés pruebas PostgreSQL PASS. Nueva prueba guarda daño del combate, aplica daño posterior fuera de combate y repite la salida: el callback duplicado conserva el HP posterior. Reemplazar sesión y repetir tampoco vuelve a aplicar la salida. Aún falta integración con lifecycle y desconexiones reales del cliente.

## Buffer de posiciones en memoria

`position_buffer` confirma batches en transacción PostgreSQL, bloquea leases vigentes y compara mapa/instancia/XYZ del baseline antes de actualizar. Ordena identidades del batch para adquirir locks consistentemente; generaciones antiguas se expulsan sin escribir. No se modifica la política explícita de posible pérdida del intervalo en un crash de este buffer en memoria.

Veinticuatro pruebas PostgreSQL PASS. Nueva prueba acredita que movimiento queda pendiente antes de flush, luego persiste una vez; otro movimiento pendiente de generación reemplazada se expulsa y no cambia posición guardada. El journal Redis de posiciones y sus barreras de recuperación siguen pendientes de adaptación.

## Journal Redis de posiciones

Recovery usa PostgreSQL con locks de lease y personaje antes de comparar baseline/current. Reconoce commit anterior al ACK y conserva conflictos para intervención; nunca aplica una generación caducada sobre otra. Redis sigue almacenando únicamente pendientes validados; PostgreSQL es la autoridad de leases y estado confirmado.

Veinticinco pruebas PASS con PostgreSQL y Redis reales. Nueva prueba en DB Redis15/namespace UUID aislado: movimiento durable sin flush se recupera a PostgreSQL, elimina su pendiente, luego otro movimiento se confirma por flush y ACK. Se limpia únicamente ese namespace de prueba. Todavía falta cubrir fallos de ACK/concurrencia de recuperación y las barreras nativas de logout/transición.

## Consumibles y acciones de inventario

Consultas de consumo curativo y destrucción/lectura de acción portadas a PostgreSQL. Consumo y HP/baseline UTC se actualizan juntos bajo lock de lease/personaje; sin schema de salud durante ejecución. Se conservan restricciones existentes de criterios/modificadores no implementados.

Veintiséis pruebas PostgreSQL PASS. Nueva prueba usa comida admitida por catálogo: consume una unidad de pila2 y cura; repetir con HP previo obsoleto rechaza sin consumir la restante. Destrucción está portada pero todavía requiere su regresión específica. Esto no implementa otros tipos de consumibles ni persistencia de accesos rápidos.

## API HTTP y timestamps

Consulta directa de propiedad portada a PostgreSQL. Respuestas convierten únicamente datetime a ISO8601 con zona horaria; evita el error de JSON al devolver personajes con created_at timestamptz y no encubre tipos desconocidos convirtiéndolos arbitrariamente a texto. Health identifica PostgreSQL en el proceso nuevo; el proceso world actual conserva el módulo antiguo hasta el cutover.

Veintisiete pruebas PostgreSQL PASS. Nueva prueba levanta una API HTTP efímera en puerto aleatorio dentro del contenedor de pruebas: POST /characters devuelve201 y timestamp UTC; GET /characters autenticado devuelve el personaje persistido. Se cierra ese servidor efímero al terminar; no se reinició world. No acredita todavía autenticación del protocolo nativo ni todos los scopes administrativos.

## Consultas del journal de builds

Consultas portadas a PostgreSQL, lock de lease/personaje en save, locks de personajes ordenados durante flush y baseline de salud UTC. Se conserva por ahora la arquitectura de snapshots pendientes Redis; no se declara resuelta su separación de commits Redis/SQL ni borrado con selección activa.

Veintiocho pruebas PASS con PostgreSQL/Redis reales: guardar deja hoja pendiente durable y overlay visible; reconstruir BuildJournal recupera ese pendiente; flush persiste la hoja y puede leerse sin overlay. Namespace UUID/Redis15 aislado. Esta prueba no inyecta fallo entre Redis y commit SQL. Antes del cutover debe resolverse esa brecha y el contrato conjunto de selección/hojas; portar placeholders no basta.

## Autoridad única de builds: decisión aplicada

Se sustituye la arquitectura descrita en la sección anterior: Store ya no usa overlay ni write-ahead Redis para builds. World ya no instancia BuildJournal ni expone su flush; se retira builds_flush del cron y de tareas admitidas. Las hojas, selección y salud se confirman directamente en una sola transacción PostgreSQL antes de responder. Esto elimina la brecha de commits de esos dominios, sin traductor, doble escritura ni fallback. El journal de posiciones sigue vigente para movimientos frecuentes.

Veintiocho pruebas PASS: se reemplazó la prueba de arquitectura retirada por fallo inyectado después de mutaciones de borrado de build activo. PostgreSQL revierte hoja, selección, revisión, HP y máximoHP y otra conexión confirma estado previo idéntico. El módulo antiguo y tests históricos que lo referencian aún deben retirarse/reorganizarse durante migración de la suite; no están conectados al runtime nuevo. Falta medir latencia de saves y probar handler nativo; world actual no se ha recargado.

## Grupos persistentes PostgreSQL

Registro JSONB transaccional con claims únicos de NPC por mapa/instancia en combat_group_members. INSERT ON CONFLICT distingue registro idempotente de roster distinto; una colisión de identidad revierte el grupo nuevo. Claim y respawn bloquean filas; defeated_at es UTC. Respawn por fecha usa SKIP LOCKED para repartir trabajo entre procesos. Retirado DDL/ALTER/PRAGMA.

Veintinueve pruebas PASS. Dos instancias de registro disputan el mismo grupo con PostgreSQL real: solo una obtiene lease; finish repetido no aplica; respawn devuelve roster. Registro repetido del mismo grupo acepta y otro grupo con el mismo NPC rechaza. Namespace de instancia aleatorio aislado. Journal Redis de grupos y lifecycle siguen pendientes; no acredita reproducción ni población natural.

## Identidad durable e integración de finish

Nuevo fight_store asigna ID identity signed32 y participante propio en una transacción con lease/personaje bloqueados. El arranque de combate del dispatcher usa ese ID en vez de aleatorio. prepare_finish marca el combate finished dentro de la misma transacción de premios y codificación; una excepción revierte también el estado durable.

Treinta pruebas PostgreSQL PASS. Nueva prueba crea dos identidades crecientes con participantes durables, revierte finished por fallo simulado del resumen y confirma placement intacto; repetir sin fallo persiste finished. Todavía faltan transición aactive, aborto de bootstrap fallido/desconexión y reconciliación de combates interrumpidos; no reiniciar world hasta completar esos caminos y los consumidores restantes.

## Activación, aborto y recuperación durable

Dispatcher activa la identidad durable al preparar readiness y aborta identidades de bootstrap rechazado. Cleanup de desconexión/selección aborta solo esa identidad propia sin modificar personaje ni combate finished; puede limpiar un combate antiguo aunque su lease ya se sustituyera. Checkpoint terminal aborted también actualiza combate. Startup recovery marca placement/active perdidos aborted y conserva finished.

Treinta y una pruebas PostgreSQL PASS. Nueva prueba cubre placement→active→aborted, aborto repetido sin efecto, rechazo de reactivar terminal y recovery que aborta placement pendiente preservando finished. Recovery es exclusivamente de arranque; no ejecutarlo contra un segundo world vivo que comparta base. Falta prueba end-to-end del dispatcher y fallo de transporte/bootstrap fuera de ValueError.

## Recibos de extracción de monstruos

Harvests usa PostgreSQL, completed_at UTC y ámbito mapa/instancia/monstruo/acción. Lock advisory transaccional por ese ámbito serializa completados entre procesos antes de comprobar cooldown; ítem y recibo confirman juntos. Retirado schema durante arranque/completado.

Treinta y dos pruebas PASS. Nueva prueba extrae una vez, rechaza repetición sin occupation, rechaza otra extracción dentro de cooldown explícito20s y acepta al transcurrirlo, con cantidad total2. Primera ejecución detectó FK de limpieza de recibos; corregido fixture y repetida suite PASS. El default actual sigue0 y aún debe migrarse la política a parámetros de base de datos: no se declara corregido el cooldown de gameplay solicitado. Falta prueba concurrente entre cuentas e instancias distintas.

### Plantaciones y crecimiento en PostgreSQL

Se retiró el DDL de arranque y las consultas SQLite de `planting.py`, `planting_cells.py` y `planting_runtime.py`. Los recibos y el outbox usan JSONB y booleanos; la plantación conserva en una transacción el recurso, el consumo y el recibo. Un bloqueo transaccional por operación serializa reintentos; la restricción de casilla rechaza conflictos sin consumir semillas. El crecimiento bloquea el recurso antes de modificarlo y registra la publicación en el outbox.

Validación en el Docker local actual, base aislada `wakemu_migration_test`: **33 pruebas de integración pasan**. La nueva prueba verifica consumo único, replay, conflicto de casilla sin consumo adicional, snapshot, crecimiento a etapa 2 y ausencia de una segunda maduración. Todavía no prueba una carrera entre dos procesos de plantación ni la entrega exactamente una vez de broadcasts. El world en ejecución conserva los módulos anteriores; el cambio completo de backend sigue pendiente.

### Grupos y preparación del arranque PostgreSQL

El world selecciona ahora `PersistentGroups` directamente. Se retiraron las tareas de volcado de grupos y el worker correspondiente; movimiento y reservas se confirman en PostgreSQL. `register_seed` conserva posiciones persistidas y valida identidad/estadísticas. `move_members` valida el roster y usa comparación JSONB en el UPDATE para rechazar movimientos obsoletos. La prueba de grupos verifica estas operaciones junto a la exclusión de reservas entre registros independientes: **33 pruebas pasan**. `!nivel` también usa SQL PostgreSQL.

Compose declara dependencia de PostgreSQL y configura `wakemu_runtime`, una base nueva sin conversión del SQLite anterior. El entrypoint aplica migraciones verificadas antes de arrancar. La imagen incluye el driver y los archivos de migración; se corrigió `.dockerignore`, que inicialmente excluía estos archivos y hacía fallar el build. `docker compose build world` pasó. El journal de posiciones usa un namespace nuevo para evitar recuperar baselines del SQLite anterior. Prueba de arranque aislada `wakemu-postgres-smoke`: cuatro migraciones aplicadas y contenedor healthy; `/health` devuelve `ok: true` y `storage: postgresql`. La instancia aislada se detuvo tras la comprobación. Cambio del world principal pendiente. Los módulos retirados de Redis/build journal y sus pruebas antiguas todavía requieren limpieza; no se afirma que la suite histórica esté migrada.

### Corte del Docker principal y restauración verificada

El 2026-10-05 se recreó `world` con la imagen PostgreSQL y se recreó `cron` para cargar el registro de tareas actualizado. `world` quedó healthy; su `/health` responde `ok: true`, `storage: postgresql`. Las cuatro migraciones existentes se validaron sin reaplicar cambios. La cuenta técnica `wakemu_scheduler`, sin rol admin, tiene el digest de la credencial privada del scheduler; los logs de cron muestran tareas `positions_flush` exitosas tras el arranque. No se imprimieron secretos ni se importaron cuentas/personajes del SQLite anterior.

Se adaptó `test_builds.py` con `postgres_case.py`: cada caso crea un esquema aislado, aplica las migraciones y lo elimina al terminar, cerrando sus pools. Las pruebas de builds, migraciones y Store suman **46 PASS** dentro de la imagen definitiva, sin driver temporal.

`pg_dump -Fc` y `pg_restore --single-transaction` restauraron `wakemu_runtime` en una base temporal. Cotejo: cuatro migraciones, 32 tablas, una cuenta técnica, un token y un grupo; la base temporal se eliminó. Backup privado: `.runtime/local/backups/postgres-runtime-20261005.dump`, permisos 0600. Esta prueba comprueba restauración del estado inicial del corte; todavía no sustituye una restauración de partida con inventario, builds y recompensas pobladas. El comando inicial de cotejo tuvo un error de quoting SQL; se corrigió y el cotejo posterior pasó.

Pendientes de E01: retirar módulos de journals Redis/builds sin consumidores runtime, adaptar la suite histórica restante y probar flujos nativos en cliente sobre PostgreSQL. No declarar completo por el healthcheck ni por este subconjunto de pruebas.

### Ampliación de cobertura histórica: capacidad y bolsas

`test_build_capacity.py` ejecuta ahora 15 casos sobre esquemas PostgreSQL aislados. El rollback de borrado se prueba con un trigger PL/pgSQL que lanza una excepción durante la escritura de salud: deben conservarse build, selección, revisión, HP e inventario. También se prueban protección de builds permanentes, límite configurable, índices hasta 127, activación sin curación y selección en reconexión. Se retiraron de esta suite las aserciones sobre el serializador de un journal que el world ya no usa.

`test_inventory_bags.py` migra cuatro casos completos a PostgreSQL: retiro/reconexión/reequipamiento preservando UID, rechazos sin pérdida de objetos, condiciones de equipamiento y bolsas apiladas. **15 PASS + 4 PASS**, adicionales a los 46 anteriores: **65 pruebas verificadas**, ejecutadas en tres conjuntos. La suite histórica completa todavía no está migrada. No hay subagentes activos, según el registro de colaboración.

### Plantación: suites históricas migradas

Se adaptaron `test_planting.py` (3 PASS) y `test_planting_runtime.py` (5 PASS) a esquemas PostgreSQL aislados. Se verifican consumo idempotente, familia nativa, reintento del outbox tras fallo del registro, rechazo por etapa inválida/oficio no aprendido, duración, cancelación, fencing de sesión, origen cambiado y crecimiento/publicación. La expiración de sesiones usa ahora TIMESTAMPTZ real. Total acumulado: **73 pruebas verificadas** en los conjuntos ejecutados; la suite completa sigue pendiente.

### Permisos y API después del corte

Se migraron `test_command_permissions.py` y `test_api_authorization.py` a esquemas PostgreSQL aislados: **9 PASS**. Cubren registro sin admin, revocación inmediata auditada, allowlist dinámica, persistencia de roles, rechazo HTTP anónimo/token inválido/jugador, acceso entre cuentas, revocación antes de ejecutar comandos encolados y alcance limitado del scheduler. JSON inválido sintácticamente ya no puede guardarse como setting JSONB; la prueba conserva políticas JSON válidas pero inválidas semánticamente, que deben fallar cerradas. Total acumulado: **82 pruebas verificadas**; no representa todavía la suite completa.

### Acciones y consumibles sobre PostgreSQL

Se migraron `test_inventory_actions.py` y `test_inventory_consumables.py`: **5 PASS**, para destrucción, replay, rechazo de unidad equipada, curación/consumo/límite y recarga persistida. La primera ejecución detectó un fixture antiguo que insertaba una build sin nivel; se corrigió el fixture con el nivel real nativo, manteniendo la validación estricta del servidor. Total acumulado: **87 pruebas verificadas**.

### Tutoriales y descubrimiento de transportes

`test_tutorials.py` y `test_transport_discovery.py` usan ahora esquemas PostgreSQL aislados: **5 PASS**, incluyendo estado de cuenta al reconectar, solicitudes inválidas, deduplicación, aislamiento entre cuentas, sesión obsoleta y paquetes nativos. Total acumulado: **92 pruebas verificadas**; suite completa pendiente.

### Persistencia del merkasaco

`test_haven_bag_store.py` se migró a esquemas PostgreSQL aislados: **11 PASS**. Cubre layouts propios y personalizados, permisos, muebles, validación de propiedad/modelo, conservación de gemas, aislamiento entre cuentas/personajes y recarga. Esto verifica persistencia y reglas existentes; no demuestra que esté implementado el flujo nativo completo de añadir merkagemas. Total acumulado: **103 pruebas verificadas**.

### Reservas y reaparición de grupos

`test_combat_group_store.py` usa esquemas PostgreSQL aislados y IDs de combate asignados por la identidad de la base: **5 PASS**. Verifica grupos derrotados tras recuperación, liberación de reservas perdidas con rechazo del lease anterior, exclusión entre registros independientes y reaparición temporizada única entre workers. El fixture inicial intentaba fijar el ID de una columna GENERATED ALWAYS; se corrigió usando INSERT RETURNING. Total acumulado: **108 pruebas verificadas**.

### Posiciones por lotes y salud

`test_position_buffer.py` usa esquemas PostgreSQL aislados: **7 PASS**. Comprueba agrupación de movimientos, posición final, generación obsoleta, rollback de conflictos de origen, aislamiento de cuentas, barrera previa al cambio de mapa, posición exterior del merkasaco y conservación de HP actualizado durante movimientos pendientes. Total acumulado: **115 pruebas verificadas**; no se declara completa la suite histórica.

### Oficios y revisión de suites pendientes

`test_profession_store.py` migra a PostgreSQL: **3 PASS**, para nivel persistido, aprendizaje sin reinicio del nivel, personajes/sesiones ajenos y resolución de monstruos por instancia. No implementa la experiencia de oficios pendiente del issue 08. Total acumulado: **118 pruebas verificadas**.

La búsqueda dirigida identificó todavía 25 archivos con patrones de fixtures SQLite antes de esta adaptación, incluyendo Store/creación, inventario/UID/elementos, salud, recompensas/checkpoints, posición Redis, comandos y suites de journals retirados. La búsqueda es un inventario parcial, no una prueba de cobertura completa; sirve para ordenar los ports restantes.

### Creación nativa de personajes

`test_creation.py` migra a PostgreSQL: **1 PASS**, con solicitudes nativas de creación, apariencia persistida, nombre duplicado/inválido, rechazo de edición de personaje existente, capacidad explícita de cinco y generación obsoleta. Total acumulado: **119 pruebas verificadas**; quedan suites y validación en cliente.

### Elementos de equipo y estado de cierre

`test_inventory_elements.py`: **3 PASS** sobre esquemas PostgreSQL, incluyendo máscaras persistidas, codecs nativos y estadísticas estables. El fixture de equipo omitía metadata de nivel; se corrigió el fixture sin relajar validaciones. Total acumulado: **122 pruebas verificadas**. Estimación de avance de E01: aproximadamente 75%, basada en backend/corte completados y trabajo pendiente de limpieza, suites y validación de partida/restauración poblada; no es una métrica automática ni una declaración de cobertura completa.

### Bloque de inventario, transferencias y reservas

Se migraron conjuntamente `test_inventory.py`, `test_inventory_move.py` y `test_inventory_uids.py`: 11 casos nuevos. Detectaron que el port había eliminado la comprobación de propiedad del contenedor en `bags`: `load` ahora incluye `character_id` y el encoder rechaza contenedores de otro personaje. También se corrigió una aserción que convertía filas dict de psycopg como si fueran tuplas SQLite.

Prueba ampliada con bolsas y Store: **48 PASS**, de los cuales 11 son nuevos; total acumulado **133 pruebas verificadas**, sin contar repetidas dos veces. El proceso world existente todavía tiene la versión anterior del módulo inventory cargada; la corrección se aplicará en el siguiente reinicio verificado. La suite completa y limpieza de módulos retirados siguen pendientes.

### Suite histórica de Store

`test_store.py` migra a PostgreSQL: **9 PASS**, para clases, capacidad configurable, apariencia, contraseñas, cuentas, consumo concurrente de tickets, reemplazo de sesión, selección/movimiento y caducidad de tokens. Se retiró el caso de migración idempotente de apariencia heredada, contrario al backend nuevo sin retrocompatibilidad. La salud inicial se coteja con el máximo inicial propio del personaje, en vez del antiguo valor fijo 50. Total acumulado: **142 pruebas verificadas**.

### Trabajo delegado y restauración poblada

Se delegaron suites de salud y limpieza de pruebas de journals a Luna low, con alcance separado de los archivos funcionales. Salud: **8 PASS**, reporte revisado; cursor psycopg registra escrituras y verifica ticks sin mutación, timestamps UTC y persistencia. Total acumulado: **150 pruebas verificadas**. La limpieza de journals sigue en curso.

Root ejecutó una restauración poblada en dos bases temporales exclusivas: migraciones, cuenta/personaje, ítem con elementos, build activa y recompensa XP1000/kamas10. `pg_dump -Fc` y `pg_restore --single-transaction` conservaron la igualdad completa del personaje leído por Store. Se verificó continuidad de `inventory_uid` y replay de recompensa sin nuevo crédito. Ambas bases temporales se eliminaron. La validación nativa en cliente y el resto de suites siguen pendientes.

### Limpieza funcional y dueño exclusivo de world

Se retiraron los módulos sin consumidores `build_journal.py`, `combat_group_redis.py` y `state_journal.py`: PostgreSQL es la autoridad de builds y grupos. Luna migró las seis suites dependientes y reportó **16 PASS**; el helper MemoryRedis de tests permanece para otras suites. No se mantiene un backend obsoleto como compatibilidad.

Se añadió `Database.acquire_runtime_lock`, con conexión dedicada y advisory lock de sesión antes de inicializar recovery del world. Evita que otro proceso con la misma base libere reservas/combates vivos al arrancar; las instancias paralelas deben usar bases aisladas. El cierre ordenado libera pool y bloqueo. Prueba de esta nueva función encargada a Luna; todavía no cargada en el world existente. Total acumulado: **166 pruebas verificadas**; limpieza de la suite completa en curso.

### Cancelación de identidad durable en fallo inesperado

La ruta de ataque del dispatcher cancela la identidad durable y libera el grupo cuando bootstrap falla con una excepción distinta de ValueError antes de producir el objeto Fight. Se mantiene el error original como fallo del flujo; no se devuelve un éxito falso. La nueva imagen se está construyendo; revisión de sintaxis y regresiones delegadas a Luna.

### Herramientas de operación

`manage_permissions.py` utiliza `WAKFU_DATABASE_URL` por defecto, conserva override explícito y cierra el pool en finally tanto en éxito como fallo. Docker incluye la herramienta, con el archivo permitido explícitamente en `.dockerignore`. README general describe PostgreSQL como base activa y SQLite únicamente como archivo histórico. Validación de sintaxis delegada; imagen con esta última actualización todavía pendiente de construir/cargar. Se delegó también la validación GUI a Luna low sobre una cuenta/PJ nuevos, sin cambios en client ni hechizos.

### Bloque delegado y herramienta de roster

Luna reportó el lote restante: 67 casos, OK con 8 omitidos por falta de URL Redis de prueba; se le encargó repetir esos casos con Redis real aislado y ejecutar descubrimiento completo. La prueba nueva de advisory lock pasó: segunda conexión rechazada, adquisición permitida tras close. El resultado agregado completo se consolidará cuando termine el descubrimiento, sin convertir skips en pruebas verificadas.

La herramienta `create-class-test-characters.py` todavía usaba SQL SQLite. Root adaptó únicamente consultas, lectura de count y cierre de pool a PostgreSQL, sin cambiar lógica de hechizos. Validación delegada.

GUI: Luna pudo abrir un perfil nuevo mediante launcher y enumerar la ventana WAKFU con System Events. `screencapture` falló con `could not create image from display`; no hubo acceso visual fiable ni prueba de login/mundo/reconexión. Se mantiene ese gate como pendiente; no es evidencia de un fallo del juego.

### Carga de limpieza y settlement atómico

Se recreó world con la imagen actualizada: healthy, migraciones verificadas (0 nuevas), bloqueo exclusivo de base y limpieza de módulos cargados. Después se detectó otra ventana de inconsistencia: recompensa/report se confirmaban antes de marcar el grupo derrotado en una conexión separada. `PersistentGroups.finish` acepta ahora conexión transaccional prestada; `prepare_finish` confirma el outcome del grupo dentro de la transacción de combate/recompensa y rollback del report. El dispatcher pasa el lease y ya no confirma el grupo por separado. Una nueva recompensa no puede confirmarse si el lease de grupo cambió; reintentos sin nuevo premio no modifican el grupo.

Regresión de éxito/rollback encargada a Luna. Este último cambio aún no está cargado en el world que acaba de reiniciar. Suite completa en contenedor efímero con estructura real de source/sniffer, sin montajes de client; resultado pendiente.

### Contrato de transacción prestada

`PersistentGroups.finish(db=...)` exige TransactionStatus.INTRANS, igual que el award: no acepta una conexión autocommit que confirmaría el grupo fuera del settlement. `prepare_finish` exige registro y lease de grupo juntos para evitar configuraciones parciales. Luna prepara la regresión con fallo del report, rollback y reintento. Cambios pendientes de carga hasta concluir ese gate.

### Healthcheck de almacenamiento real

Se detectó que `/health` devolvía ok sin consultar almacenamiento. La ruta ahora obtiene una conexión PostgreSQL, establece statement_timeout local de un segundo y ejecuta SELECT 1; los fallos devuelven HTTP503 con ok=false sin exponer la excepción. Prueba de disponibilidad/fallo encargada a Luna, sin apagar la base real. El pool conserva su timeout de adquisición: el límite de un segundo aplica a la consulta, no a esperar una conexión. Cambio todavía pendiente de carga.

Suite completa: proceso vivo confirmado en contenedor efímero `wakfu-local-world-run-64a3c2147587`, log privado `.runtime/local/full-postgres-suite.log`; su healthcheck Docker no aplica al comando unittest y no certifica fallo del servidor principal. Resultado consolidado pendiente.

### Verificación delegada y carga de settlement/healthcheck

Luna verificó tres regresiones sobre PostgreSQL: rollback de grupo y recompensa si falla el resumen, reintento que confirma ambos, healthcheck con HTTP503 al fallar conexión y transición persistida de transporte. También pasó el lote Redis real (19 pruebas). Se construyó y recreó world; Docker lo reporta healthy y el arranque valida las migraciones sin aplicar nuevas. Settlement y healthcheck están cargados.

La suite completa finalizó: **1.630 pruebas, 12 fallos, 79 errores, 1 omitida**. No es un resultado verde ni cobertura certificada. Los errores se clasificaron en 37 de area_handler no inicializado en el motor de efectos, 21 de atributos/fixtures, 9 de assets no montados, 4 de imports y 8 de políticas/metadata. No se observaron errores de conexión o SQL PostgreSQL en ese resultado. Luna adapta los fixtures de persistencia y la ejecución; las implementaciones de hechizos corresponden a otra sesión.

### Retorno de combate: HP y construcción de paquetes

Se detectó que return_to_world confirmaba HP, regeneración y recibo de salida antes de construir paquetes. Un fallo de encoder dejaba el recibo confirmado y el reintento devolvía una lista vacía. Ahora persist acepta conexión prestada con transacción activa y return_to_world construye los paquetes dentro de esa misma transacción. Pendiente regresión de rollback/reintento a cargo de Luna y carga posterior. Esto protege errores de construcción; no implica entrega de red exactamente una vez.

### Regresión de retorno y suites de persistencia

Luna ejecutó 38 pruebas: exit_reentry, combat_health, lifecycle, player_death, rewards, abandon, checkpoint, group_store y runtime_database_lock. Todas pasaron, incluida la nueva regresión de error del encoder: rollback de HP/regeneración/recibo, seguido de reintento que produce paquetes. Los fixtures de esas suites ahora usan PostgreSQL. Construcción y carga de esta corrección en curso; la suite amplia sigue delegada a Luna.

La corrección de retorno se cargó en world mediante build/recreación autorizados; world quedó healthy y validó las migraciones existentes (0 nuevas). Luna inició otra suite completa con el repositorio montado en /workspace y PYTHONPATH corregido; log privado `.runtime/local/e01-full-suite.log`. Resultado pendiente, sin declarar E01 completo.

### Resultado final de la suite delegada y separación de alcance

Luna confirmó **1.662 pruebas: 12 fallos, 59 errores, 1 omitida**. Errores exactos: 37 area_handler, 12 atributos ausentes en combate/fixtures, 8 entradas sin metadata/políticas nativas y 2 archivos de auditoría ausentes. No hubo errores PostgreSQL. Las 38 pruebas específicas de persistencia pasan. La migración del backend se considera implementada y verificada técnicamente en Docker, con restauración poblada y flujos transaccionales probados. La validación visual permanece pendiente; no se supedita el avance de los otros issues a corregir fallos del motor de hechizos que corresponde a otra sesión.

### Segundo intento visual delegado

A petición del usuario se creó otro Luna low para smoke visual. Confirmó stack healthy y comprobación loopback del perfil audit-postgres; lanzó el cliente hasta el diálogo de login. La captura macOS vuelve a fallar con could not create image from display y AX no permite observar la interfaz de juego. No creó cuenta/PJ ni realizó clicks ciegos. La persistencia visual sigue sin verificarse: este límite de observación no demuestra fallo del backend.

### Captura visual recuperada con inspector

La consulta TCC filtrada identificó org.alacritty como responsable de captura-sck; la recomendación previa de autorizar ChatGPT/Codex no estaba acreditada y queda sustituida. Se reutilizó el inspector Java del proyecto: /screen lee el canvas OpenGL, no el escritorio de macOS. Luna creó cuenta audit nueva (id2), inició cliente mediante token-file privado y guardó `.runtime/local/audit-postgres-visual/02-login-state.png`. Root abrió el PNG: selección Rubilax conectada y botón Jugar, imagen real legible. Esta evidencia resuelve la captura, todavía no acredita creación de personaje ni persistencia al reconectar. Luna continúa esas operaciones.

### Primera entrada visual acreditada

Luna creó Audiluna por UI en cuenta nueva2 y entró al mundo. Captura `.runtime/local/audit-postgres-visual/20-audiluna-created.png` muestra mapa, personaje Yopuka nivel1 y HUD60HP. La consulta PostgreSQL confirmó id1, nivel1, mapa1134, posición(-12,-8,-1), HP60/60. No se modificó el estado del personaje para fabricar esa evidencia. Se coordinó el restart de world para006; reentrada y comparación posterior pendientes.

### Persistencia visual acreditada y aceptación final

Luna capturó creación y primera entrada de Audiluna (`20-audiluna-created.png`),
selector después de reiniciarworld (`24-character-after-restart.png`) y
reentrada al mapa (`26-map-after-reentry.png`). PostgreSQL e inspector coinciden
en la posición(-14,-7,-1). Tras otro reinicio, el inventario mostró las cinco
semillas propias persistidas (`39-inventory-reloaded.png`). Las capturas están
en `.runtime/local/audit-postgres-visual/`. Se usó exclusivamente cuenta audit2.

El pendiente visual de E01 queda acreditado; la asignación de barra pertenece
aE14 y el consumo inmediato a1. Luna ejecuta el gate específico final de
persistencia sobre las ocho migraciones actuales antes de cerrarE01. La suite
completa mantiene su clasificación independiente por subsistema.

### Cierre individual de E01

Gate final sobre las ocho migraciones actuales: **77/77 pruebas**,26.144s,
en `test_combat_exit_reentry`, `test_combat_health`, `test_combat_lifecycle`,
`test_player_death`, `test_combat_rewards`, `test_combat_abandon`,
`test_fight_checkpoint_store`, `test_combat_group_store`,
`test_runtime_database_lock`, `test_postgres_migrations` y
`test_postgres_store_auth`. No se alteraron hechizos. Junto con restauración
poblada y evidencia visual anterior, acredita el corte a PostgreSQL y cierra
E01 individualmente; el objetivo de todos los issues sigue activo.

La suite amplia posterior ejecutó1703 pruebas:14 fallos,59 errores y1 omitida.
Los59 errores coinciden por ID con el baseline anterior. Dos expectativas
antiguas de salud se cotejaron y corrigieron: subida de máximo conserva herida7
(60→70,53→63), y quitar equipo conserva herida9(107/116→101/110).
Las clases de salud/equipo afectadas pasan13 pruebas dirigidas; lifecycle está
incluido en el gate77. La suite amplia no se presenta como verde ni se suman
estos grupos de pruebas superpuestos. Otros fallos siguen en sus subsistemas.
