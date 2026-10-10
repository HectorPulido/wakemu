# 38. No se pueden eliminar personajes

✅ **Estado: Solucionado totalmente.** Hector confirmó que la prueba de eliminación de personajes funciona perfectamente. Las notas de aceptación pendiente siguientes son históricas. Desplegado en merge9af0658c, migración046 aplicada; prueba nativa por socket aprobada. Falta confirmación visual del usuario. El cliente nativo del selector envía `cDN` opcode `22870` con un único `i64` big-endian de personaje. El servidor no tenía handler para ese opcode. El selector recibe la lista `23548` para volver a pintar sus personajes.

La implementación añade el handler autenticado y una baja lógica PostgreSQL: marca `characters.deleted_at`, oculta el personaje de roster/selección/búsqueda social, libera el cupo y permite volver a usar el nombre sin borrar recibos, inventario ni relaciones históricas. Se conserva la fila y su ID; la cartera de la cuenta no se modifica. La migración `046_character_deletion.sql` reemplaza la unicidad global del nombre por unicidad entre personajes activos.

La eliminación requiere estar en la pantalla de selección y rechaza una sesión seleccionada, combate, intercambio, recolección o crafting activos. Si el personaje pertenece a un grupo social, la operación lo retira dentro de la misma transacción, promueve al miembro más antiguo o disuelve un grupo que quede con menos de dos personas y publica el cambio a los miembros en línea. Tras éxito, el servidor reconstruye `12393` y `23548`; ante una operación no permitida devuelve el roster actual sin cortar la conexión.

**Validación automatizada:** 73 pruebas OK con PostgreSQL aislado y migraciones hasta046. La cobertura incluye body nativo exacto, propiedad/sesión, selección concurrente, tombstone/reapertura, cupo/nombre, conservación de XP/cartera/filas de inventario, rechazo durante combate/crafting/intercambio, salida/promoción de grupo y no resolución social del nombre retirado. El dispatcher y módulos cambiados también pasaron compilación de sintaxis en el contenedor.

Comando del gate (fuente montada de solo lectura; base exclusiva de pruebas):

```sh
docker compose run --rm --no-deps -w /workspace/server --entrypoint python3 \
  -v /Users/hectorpulido/Documents/wakfu-experiment:/workspace:ro \
  -e PYTHONPATH=/workspace/server:/workspace/server/tests:/workspace \
  -e WAKFU_POSTGRES_TEST_URL='host=postgres dbname=wakemu_migration_test user=wakemu' \
  -e WAKFU_MIGRATIONS_TEST_DIR=/workspace/server/migrations \
  -e WAKFU_DATABASE_PASSWORD_FILE=/data/secrets/postgres-password world \
  -m unittest tests.test_character_deletion tests.test_postgres_migrations \
    tests.test_postgres_store_auth tests.test_player_parties_migrations \
    tests.test_social_contacts tests.test_social_dispatch -q
```

**Aceptación manual pendiente:** entrar al selector con una cuenta de prueba que tenga dos personajes, pulsar el icono de papelera en uno y confirmar. Debe desaparecer sin reconectar; al volver a entrar debe seguir ausente, el otro personaje debe conservarse y debe poder crearse otro personaje si había alcanzado el cupo. No probar con personajes reales hasta desplegar una imagen que incluya la migración046.

Candidata selectiva845ff6fd en validación. Conserva la funciónIA de la imagenactiva sin cambios; incluye DDL045 de perfiles existente solo porque el migrador exige prefijo continuo antes046, sin activar sus consumidores nuevos. Primera candidata con salto044→046 fue rechazada automáticamente; ninguna se desplegó.

## Despliegue merge7octubre

Imagen9af0658c (wakfu-local-world:merged-verified) desplegada healthy, PostgreSQL001–048. Gate de imagen200/200; socket de recuperación agrupada, GetAll propio, reciclado, abandono y reconexión aprobado; borrado socket validado en candidata equivalente. IA y todos los módulos de combate conservados desdee18verified. Respaldo privado pre-inventory-merge-20261007.dump. Confirmación manual UI pendiente.
