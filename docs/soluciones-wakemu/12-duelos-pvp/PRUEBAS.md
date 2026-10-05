# Pruebas y aceptación — 12

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
| Aceptación | A desafía y B acepta | Mismo fight_id y ambos actores | Pendiente de implementar/verificar |
| Rechazo/timeout | B no acepta | Sin reservas permanentes | Pendiente de implementar/verificar |
| Dos invitaciones | B acepta carreras de A/C | Solo un combate reservado | Pendiente de implementar/verificar |
| Control ajeno | A manda cast actorB | Rechazado sin gastar recursos | Pendiente de implementar/verificar |
| Rendición | A abandona durante turno | Cierre coherente para ambos, mundo disponible | Pendiente de implementar/verificar |
| Reconexión | B se desconecta y vuelve | Regla de timeout/rejoin coherente, no fight duplicado | Pendiente de implementar/verificar |

## Método y criterios

Usar personaje y almacenamiento de prueba aislados. Registrar identidad de instancia, versión, estado inicial, petición, respuesta decodificada y estado durable final. Controlar reloj y RNG en los casos deterministas. Ejecutar límites de ownership, sesión obsoleta, índices/UID inválidos y payload truncado donde apliquen.

Repetir operaciones confirmadas y cortes alrededor del commit/ACK; ninguna repetición puede duplicar consumo, recompensa o efectos. Verificar observadores y reconexión cuando el caso sea multijugador. La prueba gráfica confirma integración, mientras la fixture de protocolo debe fallar si cambian layout o semántica.

Invariante: Un desafío aceptado crea un combate compartido; control y resultados no dependen del cliente que inició.

Registrar cada caso como PASS, FAIL o NO EJECUTADO, con evidencia. No convertir una omisión, un click optimista o un resultado de otro snapshot en PASS.
