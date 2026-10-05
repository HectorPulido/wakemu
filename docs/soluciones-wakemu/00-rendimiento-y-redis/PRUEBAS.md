# Pruebas y aceptación — 0

## Base existente

- [test_monster_wander.py](../../../server/tests/test_monster_wander.py): incluido en la ejecución de base registrada.
- [test_build_journal.py](../../../server/tests/test_build_journal.py): incluido en la ejecución de base registrada.
- [test_fight_checkpoint_store.py](../../../server/tests/test_fight_checkpoint_store.py): incluido en la ejecución de base registrada.
- [test_position_redis.py](../../../server/tests/test_position_redis.py): referencia existente; no ejecutado en el lote de base registrado.

El lote común descubrió **133 tests: 123 pasaron y 10 se omitieron** (Redis real); salida 0. No implica que todas las pruebas relacionadas de esta carpeta se ejecutaran, ni que los casos nuevos pasen. Ver [VALIDACION.md](../VALIDACION.md).

Comando dirigido propuesto, desde la raíz y en entorno autorizado:

```sh
PYTHONPATH=server:server/tests PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_monster_wander test_build_journal test_fight_checkpoint_store test_position_redis -q
```

## Casos específicos que deben añadirse o reproducirse

| Caso | Acción | Resultado exigido | Estado |
| --- | --- | --- | --- |
| Carga 1/16/32 grupos | Mismo mapa y jugadores; recoger latencias completas y bloqueos | Coste deja de escalar por escaneo total de cada grupo; cifras comparables y objetivo acordado | Pendiente de implementar/verificar |
| Hit Redis | Cargar tres veces un personaje con hoja pendiente y trazar SQL | Lectura cumple la política diseñada; no solo overlay después de todos los SELECT | Pendiente de implementar/verificar |
| Plazo de flush | Reloj controlado 1.199/1.200 segundos | Antes no hay commit diferido; al plazo se confirma la revisión y preserva una nueva concurrente | Pendiente de implementar/verificar |
| Crash en commit | Caída controlada antes/después de SQL y antes de limpiar Redis | Recuperación aplica una vez; inventario y balances conservados | Pendiente de implementar/verificar |
| Redis caído | Forzar error en doble y luego entorno aislado | Error explícito o recuperación segura; nunca usar estado antiguo para duplicar valor | Pendiente de implementar/verificar |
| Receptor lento | Dos clientes, uno deja de leer | El cliente sano continúa; colas acotadas y sin lock global retenido | Pendiente de implementar/verificar |

## Método y criterios

Usar personaje y almacenamiento de prueba aislados. Registrar identidad de instancia, versión, estado inicial, petición, respuesta decodificada y estado durable final. Controlar reloj y RNG en los casos deterministas. Ejecutar límites de ownership, sesión obsoleta, índices/UID inválidos y payload truncado donde apliquen.

Repetir operaciones confirmadas y cortes alrededor del commit/ACK; ninguna repetición puede duplicar consumo, recompensa o efectos. Verificar observadores y reconexión cuando el caso sea multijugador. La prueba gráfica confirma integración, mientras la fixture de protocolo debe fallar si cambian layout o semántica.

Invariante: Una solicitud de valor se aplica una vez; ninguna revisión nueva se borra por un flush antiguo; optimizar no cambia geometría legal, daños, orden de acciones o autoridad.

Registrar cada caso como PASS, FAIL o NO EJECUTADO, con evidencia. No convertir una omisión, un click optimista o un resultado de otro snapshot en PASS.
