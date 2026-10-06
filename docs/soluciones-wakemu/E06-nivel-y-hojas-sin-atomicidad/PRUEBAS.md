# Pruebas y aceptación — E06

## Revalidación PostgreSQL — 2026-10-05

Las suites se ejecutaron en contenedores `world` efímeros, con código montado read-only, PostgreSQL de pruebas y esquemas aislados por `PostgresCase` (migraciones 001–008).

Primer lote, que cubre aptitudes, comando/nivel, capacidad, builds, journal, estadísticas y publicación de equipo:

```sh
docker compose run --rm --no-deps --entrypoint python3 \
  -v "$PWD:/workspace:ro" \
  -e PYTHONPATH=/workspace:/workspace/server:/workspace/server/tests \
  -e WAKFU_POSTGRES_TEST_URL='host=postgres dbname=wakemu_migration_test user=wakemu' \
  -e WAKFU_MIGRATIONS_TEST_DIR=/workspace/server/migrations \
  -e WAKFU_DATABASE_PASSWORD_FILE=/data/secrets/postgres-password \
  world -m unittest test_aptitudes test_live_console test_build_capacity \
  test_builds test_build_journal test_equipment_stats test_equipment_full_set \
  test_equipment_full_set_ready test_equipment_combat_integration \
  test_ring_build_integration -q
```

Resultado: **54 tests OK**.

Segundo lote, centrado en el comando `!nivel` y recompensas:

```sh
docker compose run --rm --no-deps --entrypoint python3 \
  -v "$PWD:/workspace:ro" \
  -e PYTHONPATH=/workspace:/workspace/server:/workspace/server/tests \
  -e WAKFU_POSTGRES_TEST_URL='host=postgres dbname=wakemu_migration_test user=wakemu' \
  -e WAKFU_MIGRATIONS_TEST_DIR=/workspace/server/migrations \
  -e WAKFU_DATABASE_PASSWORD_FILE=/data/secrets/postgres-password \
  world -m unittest test_chat_console test_combat_rewards -q
```

Resultado: **16 tests OK**.

| Invariante | Resultado actual |
| --- | --- |
| Fallo después de preparar XP/nivel y antes del snapshot | `test_level_snapshot_failure_rolls_back_progression_and_health`: nivel, XP, HP, máximo y builds vuelven al estado previo. |
| Hoja fija 49 al pasar nivel real49→50 | `test_fixed_aptitude_level_survives_49_to_50`: comando exitoso; nivel real50, efectivo49, XP actualizado, salud y hoja conservadas tras reabrir. |
| Recompensa cruza nivel y falla actualización de salud | `test_level_health_failure_rolls_back_reward_and_wallet`: XP, nivel, wallet y recibo revierten junto con salud. |
| Recompensa de nivel con personaje herido | `test_level_reward_updates_maximum_without_healing_wounds_and_replay`: máximo cambia sin curación accidental, y la repetición no duplica recompensa. |
| Persistencia de hoja / journal | Los módulos `test_builds` y `test_build_journal` del primer lote pasaron, incluyendo guardar/reabrir y el overlay de hoja pendiente cubierto por sus fixtures configuradas. |

## Límites de la validación

Estos resultados acreditan los casos transaccionales PostgreSQL enumerados. No acreditan actualización visual de roster/cliente, todos los consumidores de `effective_level` durante combate, todas las modalidades de hoja, ni el flujo completo de recompensas hasta el ACK del cliente. El primer comando incluye el módulo `test_live_console`; el comando de administración `!nivel` está cubierto por `test_chat_console` en el segundo.
