# Pruebas y aceptación — 33

## Revalidación PostgreSQL — 2026-10-05

Se ejecutaron las suites de abandono, retorno, resultado, salud, checkpoint, grupo y transportes con PostgreSQL y migraciones 001–008. Cada test `PostgresCase` usa un esquema aleatorio aislado.

```sh
docker compose run --rm --no-deps --entrypoint python3 \
  -v "$PWD:/workspace:ro" \
  -e PYTHONPATH=/workspace:/workspace/server:/workspace/server/tests \
  -e WAKFU_POSTGRES_TEST_URL='host=postgres dbname=wakemu_migration_test user=wakemu' \
  -e WAKFU_MIGRATIONS_TEST_DIR=/workspace/server/migrations \
  -e WAKFU_DATABASE_PASSWORD_FILE=/data/secrets/postgres-password \
  world -m unittest test_combat_abandon test_combat_exit_reentry \
  test_combat_lifecycle test_combat_health test_combat_results \
  test_combat_rewards test_combat_group_store test_fight_checkpoint_store \
  test_native_transports test_transports test_transport_discovery \
  test_runtime_database_lock -q
```

Resultado: **64 tests OK**.

| Recorrido | Evidencia actual |
| --- | --- |
| Abandono de colocación/combate y retorno | `test_combat_abandon`: dueño y fight ID se validan; los flags 0 y 1 se aceptan para el abandono ya autorizado; IDs ajenos, payload inválido y repetición no aplican una segunda salida. `prepare` confirma `combat_fights.status='aborted'` junto con HP/recibo, antes del checkpoint o ACK. No concede recompensas. |
| Fallo al persistir estado abortado | `test_status_update_failure_rolls_back_health_receipt_and_runtime_state`: el fallo de SQL revierte HP/recibo y conserva estado de fight, ACK y pendientes en memoria. |
| Fight durable ya terminado | `test_finished_durable_fight_rejects_abandon_without_any_mutation`: rechaza abandono y conserva HP/recibo y FSM. |
| HP y persistencia | `test_combat_health`: daño de salida se conserva; fallo de encoder revierte salud y recibo para reintentar. |
| Desconexión atómica y retry | `test_abort_sql_failure_rolls_back_hp_receipt_and_fight_then_retry_succeeds`: error al escribir el status revierte HP, recibo y fight; un reintento guarda el daño y aborta el fight. `test_borrowed_abort_rejects_autocommit_connection` verifica que el helper exija una transacción activa. |
| Lease obsoleta | `test_replaced_lease_and_stale_health_do_not_overwrite_new_state`: la salida obsoleta no toca HP ni recibos del personaje actual y solo termina la identidad durable del fight viejo; el fight nuevo sigue en colocación. |
| Abandono → checkpoint terminal → retorno → transporte → nuevo combate | `test_combat_exit_reentry.test_abandon_return_allows_native_transport_and_new_durable_fight`: checkpoint queda `aborted`, se libera el lease del grupo, el ZAAP nativo resuelve desde la posición exterior, `transition_map` persiste el destino y otro fight durable puede pasar a `active`. No se registra recompensa para el fight abandonado. |
| Desconexión sin callback 12925 | `test_combat_exit_reentry.test_disconnect_without_return_callback_keeps_abort_terminal_and_recoverable`: el checkpoint terminal sobrevive reopen/recovery, mantiene HP y permite crear otro fight después de abrir una sesión y seleccionar el personaje. |
| Nuevo Ready tras abandono | `test_combat_exit_reentry.test_active_abort_return_and_new_ready_preserve_own_damage`: se construye un fight/Runtime nuevo y conserva el HP propio. |
| Leases de grupo/checkpoint y cierre normal | `test_combat_group_store`, `test_fight_checkpoint_store`, `test_combat_lifecycle`, `test_combat_rewards` y `test_runtime_database_lock` pasan en el mismo lote. |
| Rutas nativas de transporte | `test_native_transports`, `test_transports` y `test_transport_discovery` validan IDs, destinos, poses, descubrimiento y persistencia de transición. |

## Alcance pendiente de evidencia

El recorrido combinado nuevo llama directamente a las funciones de abandono/retorno, checkpoint, grupo, ZAAP y transición de mapa. No dispara 13952/12925 mediante el dispatcher de `local_game_server` ni reproduce visualmente la interacción del cliente. El outcome abortado ya no depende del checkpoint posterior: la prueba cubre la atomicidad de HP/recibo/estado SQL y una desconexión después del checkpoint terminal. Aún no inyecta una falla posterior al commit de abandono durante la liberación del grupo/checkpoint del handler. Este resultado acredita las transiciones de backend y el caso requerido de nuevo combate más transporte, pero no certifica por sí solo el recorrido de socket/GUI ni esa falla del handler.

El runtime rechaza el abandono parcial de un combate con más de un participante controlado; esta política no se extiende aquí a un cierre multiplayer por participante. La recuperación sin 12925 se prueba desde el checkpoint terminal simulado y un `reopen`, no matando el proceso servidor durante el callback.
