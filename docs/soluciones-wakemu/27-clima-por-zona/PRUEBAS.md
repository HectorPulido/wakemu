# Pruebas y aceptación — 27

## Automatizadas

Gate Docker PostgreSQL aislado, con las59 migraciones presentes al correrlo (incluida la058 de forecast):

```sh
docker compose run --rm --no-deps --entrypoint python3 -w /workspace/server \
  -v /Users/hectorpulido/Documents/wakfu-experiment:/workspace:ro \
  -e PYTHONPATH=/workspace/server:/workspace/server/tests \
  -e WAKFU_POSTGRES_TEST_URL='host=postgres dbname=wakemu_migration_test user=wakemu' \
  -e WAKFU_MIGRATIONS_TEST_DIR=/workspace/server/migrations \
  -e WAKFU_DATABASE_PASSWORD_FILE=/data/secrets/postgres-password \
  world -m unittest test_territory_weather_forecast \
    test_territory_weather_local_policy test_territory_weather \
    test_territory_weather_transitions test_territory_weather_publish \
    test_territory_weather_movement_dispatch test_planting_weather_dispatch \
    test_ecology_context test_global_tasks test_postgres_migrations
```

Resultado del gate actual: **76/76 OK**. Cubre el layout13895 contra vector golden, límites y payload vacío, política SQL por instancia, reemplazo monotónico, carrera de primera escritura, outbox superseded/retry, revalidación de lease/región al publicar, restricciones SQL, snapshot ecológico scoped y envío en orden12789→13948→13895, además de las suites de clima/flora/tareas/migraciones.

El probe Java offline `ForecastNativeProbe` también pasó contra el JAR del cliente instalado: `PASS: installed bRV.fe decoded named 13895 local-policy vector`. El vector prueba parser/layout, no origen oficial de los datos.

El smoke TLS completo pasó contra `wakemu-sublimation-weather-level-candidate:20261007-final2`, digest `e839fd35a2c123b8c83006528cfabc8f7bb5c8e5c3d0973f347ffcadc5321742`, en DB desechable `wakemu_candidate_sublimation_059_20261007`. Verificó bootstrap12789/13948/13895 en dos regiones e instancia no-cero, clear vacío para región sin forecast, actualización v2 del outbox solo a región A, ack durable, ausencia de broadcast a B, reconexión y resolver de plantación. Usa forecast local sintético; no acredita origen ni unidades upstream. La imagen no se desplegó.

## Aceptación manual

1. En el mapa1134 ejecuta `!pos` y `!tp 1134 -39 -72 47`; abre **Panel meteorológico** y anota lo visible.
2. Ejecuta `!tp 1134 -23 -143 70`; confirma que el estado corresponde a la segunda región. Regresa con `!tp 1134 -39 -72 47` y comprueba que el primero conserva su estado.
3. Sal del mundo y vuelve a entrar en cada región; el estado13948 debe coincidir con el estado persistido.
4. Tras la integración del bootstrap de forecast, configura una previsión local de prueba para un ámbito, entra al ámbito y comprueba los días/temporada. Entra a otro ámbito sin previsión y comprueba que el paquete vacío retira cualquier dato anterior.

Las coordenadas son casillas transitables conocidas. Los pasos1–3 verifican el clima actual; el paso4 no está habilitado hasta que root revise la conexión de13895 y configure datos de prueba. No registrar forecast como aprobado basándose solo en el codec.
