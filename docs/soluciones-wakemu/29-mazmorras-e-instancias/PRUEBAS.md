# Pruebas y aceptación — 29

## Base existente

- [test_combat_groups.py](../../../server/tests/test_combat_groups.py): incluido en la ejecución de base registrada.
- [test_combat_rewards.py](../../../server/tests/test_combat_rewards.py): incluido en la ejecución de base registrada.
- [test_haven_bag.py](../../../server/tests/test_haven_bag.py): incluido en la ejecución de base registrada.

El lote común descubrió **133 tests: 123 pasaron y 10 se omitieron** (Redis real); salida 0. No implica que todas las pruebas relacionadas de esta carpeta se ejecutaran, ni que los casos nuevos pasen. Ver [VALIDACION.md](../VALIDACION.md).

Comando dirigido propuesto, desde la raíz y en entorno autorizado:

```sh
PYTHONPATH=server:server/tests PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_combat_groups test_combat_rewards test_haven_bag -q
```

## Casos específicos que deben añadirse o reproducirse

La suite `server/tests/test_dungeon_instances.py` cubre el componente durable: plantilla frente a ID vivo, reintento idempotente, propiedad de party/leader, generaciones y miembros online, callback de autorización, rollback tras fallo durante inserción de miembros y carrera de entradas. Requiere PostgreSQL aislado; el gate actual aplicó el prefijo contiguo 001–067. No prueba el transportador ni una mazmorra jugable.

Actualización 2026-10-07: `test_generic_transports.py::test_jalato_dungeon_template_is_not_a_live_instance_transport` comprueba el cuerpo nativo de 12296 contra la entrada normal candidata (mapa 527, objeto 26842, destino 2504), verifica que `cyZ=91` es la plantilla de destino y confirma que el resolver genérico rechaza el criterio `not IsNeoServer()` sin cambiar la posición del personaje. `test_dungeon_instances.py` y `test_dungeon_transport.py` cubren la transición party-owned: autorización y proximidad obligatorias, destino limitado al catálogo nativo, creación/reutilización de un ID vivo distinto de `cyZ`, traslado de todos los miembros en la misma transacción, reintento idempotente, carrera de entradas y rollback completo si falla el movimiento de un miembro. El ID de plantilla no autoriza la membresía del run. Gate ejecutado en el contenedor world existente usando solo esquemas `PostgresCase` aislados de `wakemu_migration_test` y migraciones 001–067:

```sh
docker exec wakfu-local-world-1 sh -lc 'cd /tmp/wakemu-dungeon-gate/server && PYTHONPATH=/tmp/wakemu-dungeon-gate/server/tests:/tmp/wakemu-dungeon-gate/server WAKFU_POSTGRES_TEST_URL="host=postgres dbname=wakemu_migration_test user=wakemu" WAKFU_MIGRATIONS_TEST_DIR=/tmp/wakemu-dungeon-gate/server/migrations WAKFU_DATABASE_PASSWORD_FILE=/data/secrets/postgres-password python3 -m unittest test_dungeon_instances test_dungeon_transport test_generic_transports -q'
```

Resultado de ese gate: 20/20 PASS sobre migraciones 001–067. No se alteró la base runtime y el gate no habilita el transporte. La migración 068 agrega configuración explícita del modo. La evidencia cliente establece `eEL.IS_NEO_SERVER`, clave `server.group.isneo`, default `false`; el parser reconoce el criterio como tipo 325. El visitor que conecta ambos no está en los artefactos disponibles, así que la equivalencia del helper está documentada como inferencia y el dispatcher continúa sin caller.

Gate posterior de configuración 068: `test_dungeon_criteria test_dungeon_instances test_dungeon_transport`, ejecutado en el contenedor world existente sobre esquemas `PostgresCase` aislados de `wakemu_migration_test` y migraciones 001–068. Resultado 22/22 PASS. Artifact: `.runtime/local/dungeon-mode-gate-20261007.txt`. El helper cubre normal/Neo, persistencia del valor, ausencia o corrupción del setting y rechazo de predicados no implementados. No se conectó el dispatcher ni se escribió en la base runtime. La evidencia/fuentes del modo y composición están resumidas en [probe-configuracion-is-neo-server.json](probe-configuracion-is-neo-server.json) y [probe-composicion-encuentros.json](probe-composicion-encuentros.json).

La evidencia de composición sigue siendo limitada: definición 90 declara mapa interior 1086 y referencias `[1,2,3,39,41,44]`, pero no distribuye cantidades ni monstruos por sala. La clase nativa aKU.cno() entrega esas referencias a la búsqueda del catálogo; no produce la composición de encuentros. El mapa de combate exportado declara explícitamente geometría estática, sin actores dinámicos. El catálogo de teletransportadores acredita enlaces/sectores, no encuentros. El siguiente contrato de integración es interceptar únicamente la ruta normal cotejada, evaluar el modo y la proximidad desde autoridad de servidor, crear o recuperar el run de la party y mover a todos sus miembros usando el `instance_id` generado. No enviar 91 al campo de instancia ni inferir encuentros de la lista de referencias.

| Caso | Acción | Resultado exigido | Estado |
| --- | --- | --- | --- |
| Entrada party | Dos miembros aceptados | Misma instance_id | Pendiente de implementar/verificar |
| Llave/requisito | Entrada inválida | Sin consumo ni instancia parcial | Pendiente de implementar/verificar |
| Victoria sala | Evento duplicado | Un progreso y grupos siguientes una vez | Pendiente de implementar/verificar |
| Abandono | Salir en sala/combate | Estado world disponible conforme 33 | Pendiente de implementar/verificar |
| Recovery | Volver a instancia viva/cerrada | Rejoin o salida segura, sin reset loot | Pendiente de implementar/verificar |
| Dos parties | Misma mazmorra/mapa | Población/progreso aislados | Pendiente de implementar/verificar |

## Método y criterios

Usar personaje y almacenamiento de prueba aislados. Registrar identidad de instancia, versión, estado inicial, petición, respuesta decodificada y estado durable final. Controlar reloj y RNG en los casos deterministas. Ejecutar límites de ownership, sesión obsoleta, índices/UID inválidos y payload truncado donde apliquen.

Repetir operaciones confirmadas y cortes alrededor del commit/ACK; ninguna repetición puede duplicar consumo, recompensa o efectos. Verificar observadores y reconexión cuando el caso sea multijugador. La prueba gráfica confirma integración, mientras la fixture de protocolo debe fallar si cambian layout o semántica.

Invariante: Una party comparte una instancia; sus salas/premios no se mezclan con otras ni se duplican al entrar.

Registrar cada caso como PASS, FAIL o NO EJECUTADO, con evidencia. No convertir una omisión, un click optimista o un resultado de otro snapshot en PASS.
