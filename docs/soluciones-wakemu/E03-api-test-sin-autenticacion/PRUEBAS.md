# Pruebas y aceptación — E03

## Revalidación del backend PostgreSQL — 2026-10-05

El lote dirigido se ejecutó contra el checkout montado en el contenedor `world`, con PostgreSQL y las migraciones actuales 001–008. `PostgresCase` crea un esquema aleatorio por prueba y aplica todas las migraciones; no modifica las cuentas del mundo activo.

Comando ejecutado:

```sh
docker compose run --rm --no-deps --entrypoint python3 \
  -v "$PWD:/workspace:ro" \
  -e PYTHONPATH=/workspace:/workspace/server:/workspace/server/tests \
  -e WAKFU_POSTGRES_TEST_URL='host=postgres dbname=wakemu_migration_test user=wakemu' \
  -e WAKFU_MIGRATIONS_TEST_DIR=/workspace/server/migrations \
  -e WAKFU_DATABASE_PASSWORD_FILE=/data/secrets/postgres-password \
  world -m unittest test_api_authorization test_command_permissions \
  test_chat_console test_global_tasks -q
```

Resultado: **20 tests OK**.

| Caso | Resultado verificado |
| --- | --- |
| Sesiones, tareas, comandos y resultados sin token o con token inválido | `401`; sin callback, recibo de consola ni mutación |
| Token de jugador en rutas administrativas | `403`; sin efectos |
| Comando sobre personaje de otra cuenta y lectura de recibo ajeno | `403` |
| Revocación de rol o token con comando encolado | La ejecución posterior falla; callback no corre |
| Principal scheduler | Solo ejecuta `positions_flush`; no consulta sesiones ni ejecuta comandos/tareas por personaje; revocación bloquea nuevos trabajos |
| Registro, allowlist y revocación administrativa | El registro no crea admin; allowlist inválida falla cerrada; cambios de rol quedan auditados |
| Consola de chat y persistencia de comandos | Operaciones autorizadas persisten; payload, lease o propiedad inválidos no conceden cambios |
| `/health` | Público; `200` con DB disponible y respuesta genérica `503` ante fallo de conexión |

Las pruebas de HTTP crean cuentas y roles ficticios únicamente dentro de esquemas aislados. No se otorgaron roles admin a usuarios reales.

## Cobertura anterior

`test_chat_console.py` y la matriz de rutas ya tenían cobertura previa; el registro histórico de 133 pruebas no certificaba por sí solo los casos E03. La revalidación PostgreSQL anterior es el resultado vigente para el backend. La interfaz gráfica de una partida es evidencia separada y no forma parte de estas 20 pruebas.
