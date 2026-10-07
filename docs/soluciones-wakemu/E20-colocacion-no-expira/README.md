# E20 — La colocación permanece bloqueada al llegar a cero

**Estado: Solucionado totalmente.** Cierre confirmado por el usuario tras probar el inicio automático. Los hechizos de los monstruos quedan fuera del alcance de este issue y no deben modificarse como parte de esta corrección.

## Reproducción

El usuario observó a Audiluna en colocación con el contador en0 durante un tiempo prolongado. Al pulsar «Listo», el combate inició. No se atribuye el clic al agente de pruebas.

## Causa cotejada

`combat_bootstrap.placement_messages` publica13684 con `fight.id` y `duration_ms`, cuyo default es60000. El dispatcher prepara el combate únicamente al recibir12523. `session.idle` comprueba caducidad de turnos a través de `fight_messages`, que todavía no existe durante colocación. No hay deadline de colocación ni transición al agotarse ese contador.

## Corrección requerida

Persistir la política de duración en `settings` PostgreSQL; validar enteros y límites. Al crear el combate, congelar duración y registrar un deadline monotónico asociado a su identidad. Usar la misma duración en13684. Al vencer, preparar a los participantes mediante el mismo camino validado que usa «Listo», sin duplicar inicialización de clases ni conceder recompensas. El plazo debe comprobarse durante idle y durante tráfico continuo, y debe cancelarse al abandonar, terminar o reemplazar el combate.

## Pruebas de aceptación

- Antes del deadline conserva colocación; al vencer inicia sin12523.
- «Listo» anticipado y vencimiento concurrente no duplican inicialización/paquetes.
- Tráfico continuo no impide vencer; una sesión sustituida no inicia el combate anterior.
- Cambiar política afecta combates nuevos; contador y plazo del existente conservan su duración inicial.
- Error de inicialización no confirma una fase activa parcial; el error queda registrado.

## Estado

Defecto reproducido por el usuario y causa confirmada en código. Implementación cargada y verificada en cliente: migración009, política `combat_placement_duration_ms`, deadline monotónico por identidad y transición compartida `apply_readiness`. La política se valida antes de crear la identidad durable; activar PostgreSQL precede al reemplazo de fase/runtime en memoria. Si falla la inicialización, se registra el rechazo una vez y sigue disponible «Listo» manual; no se reintenta en cada paquete. Hechizos y efectos continúan bajo responsabilidad de la otra sesión; esta corrección coordina fases y temporizadores.

Gate de `test_placement_deadline test_combat_bootstrap test_postgres_migrations test_combat_orientation`: **21/21 pruebas** en Docker/PostgreSQL aislado. Verifica fronteras, claim único, cancelación por fase/identidad, política inválida y duración congelada, lease antes de vencimiento, llamadas idle durante receive/tráfico y carrier13684. Un trigger SQL rechaza la activación y demuestra que combate/mensajes originales, estado durable y ausencia de paquetes se conservan. Compilación y diff-check pasan.

Imagen `33a78a4819e2b791eade0c67e02193a693de8545d51d649a4bfa7651dfae1f7f` cargada, healthy y `/health` PostgreSQL ok. Política real60000 y vencimiento visual verificados. La ruta vigente admite un participante controlado y no certifica expiración multijugador futura. El evento `combat_placement_expired` indica procesamiento del plazo de este dueño; para acreditar inicio también se exige `combat_test_active` y estado visible activo.

## Prueba real verificada

Audiluna nivel100 inició el combate2; Luna preservó la captura de colocación a58 segundos en `.runtime/local/audit-postgres-visual/e20-placement-start.png` y no pulsó «Listo». El log del servidor registra `combat_test_active` a2026-10-06T04:23:35.149193Z y `combat_placement_expired` a04:23:35.644242Z para combate2/personaje1. La captura posterior `.runtime/local/audit-postgres-visual/e20-after-wait.png`, inspeccionada por el agente principal, muestra «Turno3», «¡Tu turno!» y «Pasar tu turno» con28 segundos: acredita el cambio visible a combate activo sin el clic manual. El defecto original queda corregido y reproducido en el recorrido de un participante controlado; la futura colocación multijugador necesita su propia aceptación.


## Prueba del usuario y correlación de logs — 6 de octubre

Fight9/Audiluna: colocación07:00:39 UTC; transición automática a activo07:01:39 y `combat_placement_expired`07:01:40. El usuario confirma que inicia al agotar el tiempo. Los Tofus no actuaron: logs `combat_monster_attack_rejected` con `No audited attack for this monster reference/level`, seguidos de paso de turno. Esta observación queda registrada como contexto; por instrucción del usuario, los hechizos de monstruos no se investigan ni modifican dentro de este trabajo.

La interrupción observada después coincide con `server_shutdown`07:01:48 UTC, provocado por la recarga autorizada del root para cambios de flora. No demuestra un reinicio espontáneo del combate. **Estado actual: Solucionado totalmente**, conforme a la confirmación del usuario. La futura aceptación multijugador corresponde a su propio alcance y no mantiene abierto E20.


## Cierre confirmado por el usuario

**Solucionado totalmente.** El6 de octubre el usuario confirmó el inicio automático al vencer el contador y solicitó cerrar E20. La investigación de hechizos de monstruos queda expresamente fuera de este alcance y fue detenida. La interrupción de fight9 fue la recarga del servidor documentada arriba. Las notas previas de estado parcial quedan como historial, sustituidas por este cierre.
