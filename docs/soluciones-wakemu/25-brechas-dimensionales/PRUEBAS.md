# Pruebas y aceptación — 25

## Base existente

- [test_combat_groups.py](../../../server/tests/test_combat_groups.py): incluido en la ejecución de base registrada.
- [test_combat_rewards.py](../../../server/tests/test_combat_rewards.py): incluido en la ejecución de base registrada.

El lote común descubrió **133 tests: 123 pasaron y 10 se omitieron** (Redis real); salida 0. No implica que todas las pruebas relacionadas de esta carpeta se ejecutaran, ni que los casos nuevos pasen. Ver [VALIDACION.md](../VALIDACION.md).

Comando dirigido propuesto, desde la raíz y en entorno autorizado:

```sh
PYTHONPATH=server:server/tests PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_combat_groups test_combat_rewards -q
```

## Casos específicos que deben añadirse o reproducirse

| Caso | Acción | Resultado exigido | Estado |
| --- | --- | --- | --- |
| Entrada dos jugadores | Acceso legal y party | Misma instancia y definición | Pendiente de implementar/verificar |
| Requisito inválido | Nivel/cupo inaccesible | No teleporte ni consumo | Pendiente de implementar/verificar |
| Oleada repetida | Retry evento victoria | No grupos duplicados | Pendiente de implementar/verificar |
| Reloj vence | Avanzar reloj controlado | Resultado según regla conocida | Pendiente de implementar/verificar |
| Abandono/rejoin | Jugador vuelve durante o después | Progreso conservado o salida terminal | Pendiente de implementar/verificar |
| Reward retry | Cerrar dos veces misma brecha | Premio una vez y reservas liberadas | Pendiente de implementar/verificar |

## Método y criterios

Usar personaje y almacenamiento de prueba aislados. Registrar identidad de instancia, versión, estado inicial, petición, respuesta decodificada y estado durable final. Controlar reloj y RNG en los casos deterministas. Ejecutar límites de ownership, sesión obsoleta, índices/UID inválidos y payload truncado donde apliquen.

Repetir operaciones confirmadas y cortes alrededor del commit/ACK; ninguna repetición puede duplicar consumo, recompensa o efectos. Verificar observadores y reconexión cuando el caso sea multijugador. La prueba gráfica confirma integración, mientras la fixture de protocolo debe fallar si cambian layout o semántica.

Invariante: Oleada/objetivo cambia una vez por evento; todos ven misma instancia y cierre terminal.

Registrar cada caso como PASS, FAIL o NO EJECUTADO, con evidencia. No convertir una omisión, un click optimista o un resultado de otro snapshot en PASS.
