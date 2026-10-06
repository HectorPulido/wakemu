# Pruebas y aceptación — E01

## Base existente

- [test_build_journal.py](../../../server/tests/test_build_journal.py): incluido en la ejecución de base registrada.
- [test_planting_runtime.py](../../../server/tests/test_planting_runtime.py): incluido en la ejecución de base registrada.

El lote común descubrió **133 tests: 123 pasaron y 10 se omitieron** (Redis real); salida 0. No implica que todas las pruebas relacionadas de esta carpeta se ejecutaran, ni que los casos nuevos pasen. Ver [VALIDACION.md](../VALIDACION.md).

Comando dirigido propuesto, desde la raíz y en entorno autorizado:

```sh
PYTHONPATH=server:server/tests PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_build_journal test_planting_runtime -q
```

## Casos específicos que deben añadirse o reproducirse

| Caso | Acción | Resultado exigido | Estado |
| --- | --- | --- | --- |
| Backup concurrente | Fixturetemporal conWAL ywrites | Backup íntegro concommits esperados | Pendiente de implementar/verificar |
| Integridad | Copiaverificada | quick/integrity/foreignkeys sinerror o detalle claro | Pendiente de implementar/verificar |
| ReconciliarRedis | Baseline anterior/nuevo | Sin replay sobre SQL incompatible | Pendiente de implementar/verificar |
| Objeto duplicado | Copias conUID/recibo repetidos | Validación detecta antes de cutover | Pendiente de implementar/verificar |
| Planta recuperada | Timer/resource de copia sana | Etapas pueden avanzar sinmalformed | Pendiente de implementar/verificar |
| Rollback | Ensayo autorizado sobre copia | Restore reproduceestado conocido, no datos mezclados | Pendiente de implementar/verificar |

## Método y criterios

Usar personaje y almacenamiento de prueba aislados. Registrar identidad de instancia, versión, estado inicial, petición, respuesta decodificada y estado durable final. Controlar reloj y RNG en los casos deterministas. Ejecutar límites de ownership, sesión obsoleta, índices/UID inválidos y payload truncado donde apliquen.

Repetir operaciones confirmadas y cortes alrededor del commit/ACK; ninguna repetición puede duplicar consumo, recompensa o efectos. Verificar observadores y reconexión cuando el caso sea multijugador. La prueba gráfica confirma integración, mientras la fixture de protocolo debe fallar si cambian layout o semántica.

Invariante: Recovery nunca inventa objetos/progreso; la copia reparada se valida antes de sustituir la autoridad.

Registrar cada caso como PASS, FAIL o NO EJECUTADO, con evidencia. No convertir una omisión, un click optimista o un resultado de otro snapshot en PASS.

## Suite completa del servidor — 5 de octubre de 2026

Se ejecutó el descubrimiento completo en un contenedor efímero con el checkout montado en solo lectura, PostgreSQL `wakemu_migration_test` y Redis DB 15. El log privado está en `.runtime/local/full-postgres-suite-current.log`.

```sh
docker compose run --rm --no-deps --entrypoint python3 \
  -v "$PWD:/workspace:ro" \
  -e PYTHONPATH=/workspace:/workspace/server:/workspace/server/tests \
  -e WAKFU_POSTGRES_TEST_URL='host=postgres dbname=wakemu_migration_test user=wakemu' \
  -e WAKFU_MIGRATIONS_TEST_DIR=/workspace/server/migrations \
  -e WAKFU_DATABASE_PASSWORD_FILE=/data/secrets/postgres-password \
  -e WAKFU_REDIS_TEST_URL=redis://redis:6379/15 \
  world -m unittest discover -s /workspace/server/tests -q
```

Resultado: **1,737 tests; 12 FAIL, 59 ERROR, 1 omitido; salida 1**. No se observaron trazas de fallo PostgreSQL, migración ni Redis en los errores de unittest. La ejecución acotada relacionada con cleanup, journal Redis, mundo/chat y autorización pasó **88/88**; no sustituye el resultado rojo de la suite completa.

Los errores completos se concentran en suites de combate: 37 `UnboundLocalError` de `area_handler` (displacement 2, effect runtime 18, runtime adapter 2, state decurse 7 y state level/group 8); 12 `AttributeError` por fixtures/modelos sin `turn_count` (8), `native_obstacle_id` (3) o `RegisteredSummonAuthority.decks` (1); 8 `ValueError` por políticas nativas ausentes (routing de dueño de entrega 2, build metadata 4, límite de lanzamiento propio 1 y propagación de summon sin auditar 1); y 2 artefactos ausentes (`cinetosis-fulgor-runtime-audit.json` y `.runtime/local/hud-threshold-runtime.json`). Los 12 `FAIL` son también de comportamiento/expectativas de combate: eventos de displacement (3), heart-blood (2), ordinary healing events (2), diagnóstico de efecto 949 (1), autocast/LOS (1), pasiva de inicio Iop (1), rama crítica del arma (1) y registro de características de efecto (1).

Esta suite no atribuye esos fallos a persistencia PostgreSQL. Mantenerlos como fallos abiertos de sus módulos; no retirar assertions ni presentar la suite completa como verde. E01 se evalúa además por su gate PostgreSQL específico, restauración poblada y validación visual documentados en [IMPLEMENTACION.md](IMPLEMENTACION.md).
