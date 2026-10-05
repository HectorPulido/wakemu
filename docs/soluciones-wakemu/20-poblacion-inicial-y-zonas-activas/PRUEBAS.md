# Pruebas y aceptación — 20

## Base existente

- [test_monster_wander.py](../../../server/tests/test_monster_wander.py): incluido en la ejecución de base registrada.
- [test_planting_runtime.py](../../../server/tests/test_planting_runtime.py): incluido en la ejecución de base registrada.
- [test_combat_group_store.py](../../../server/tests/test_combat_group_store.py): incluido en la ejecución de base registrada.

El lote común descubrió **133 tests: 123 pasaron y 10 se omitieron** (Redis real); salida 0. No implica que todas las pruebas relacionadas de esta carpeta se ejecutaran, ni que los casos nuevos pasen. Ver [VALIDACION.md](../VALIDACION.md).

Comando dirigido propuesto, desde la raíz y en entorno autorizado:

```sh
PYTHONPATH=server:server/tests PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_monster_wander test_planting_runtime test_combat_group_store -q
```

## Casos específicos que deben añadirse o reproducirse

| Caso | Acción | Resultado exigido | Estado |
| --- | --- | --- | --- |
| Primera entrada | Zona nunca seeded | Lote pequeño una vez | Pendiente de implementar/verificar |
| Segunda entrada | Entrar/salir repetidamente | No lote adicional | Pendiente de implementar/verificar |
| Ausencia prolongada | Reloj externo avanza | Sin movimiento, crecimiento o reproducción acordados | Pendiente de implementar/verificar |
| Regreso | Zona pausada vuelve activa | Continúa remaining, no crecimiento acumulado | Pendiente de implementar/verificar |
| Dos jugadores | Sale uno y queda otro | Zona sigue activa | Pendiente de implementar/verificar |
| Exterminio | Matar todo y reentrar | Sin respawn oculto, regla 3 respetada | Pendiente de implementar/verificar |

## Método y criterios

Usar personaje y almacenamiento de prueba aislados. Registrar identidad de instancia, versión, estado inicial, petición, respuesta decodificada y estado durable final. Controlar reloj y RNG en los casos deterministas. Ejecutar límites de ownership, sesión obsoleta, índices/UID inválidos y payload truncado donde apliquen.

Repetir operaciones confirmadas y cortes alrededor del commit/ACK; ninguna repetición puede duplicar consumo, recompensa o efectos. Verificar observadores y reconexión cuando el caso sea multijugador. La prueba gráfica confirma integración, mientras la fixture de protocolo debe fallar si cambian layout o semántica.

Invariante: Seeding una vez por zona/version; estado vacío no se rellena implícitamente al entrar.

Registrar cada caso como PASS, FAIL o NO EJECUTADO, con evidencia. No convertir una omisión, un click optimista o un resultado de otro snapshot en PASS.
