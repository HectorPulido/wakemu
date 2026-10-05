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
