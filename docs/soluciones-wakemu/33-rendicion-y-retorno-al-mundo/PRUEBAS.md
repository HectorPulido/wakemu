# Pruebas y aceptación — 33

## Base existente

- [test_combat_abandon.py](../../../server/tests/test_combat_abandon.py): referencia existente; no ejecutado en el lote de base registrado.
- [test_combat_results.py](../../../server/tests/test_combat_results.py): referencia existente; no ejecutado en el lote de base registrado.
- [test_combat_lifecycle.py](../../../server/tests/test_combat_lifecycle.py): referencia existente; no ejecutado en el lote de base registrado.

El lote común descubrió **133 tests: 123 pasaron y 10 se omitieron** (Redis real); salida 0. No implica que todas las pruebas relacionadas de esta carpeta se ejecutaran, ni que los casos nuevos pasen. Ver [VALIDACION.md](../VALIDACION.md).

Comando dirigido propuesto, desde la raíz y en entorno autorizado:

```sh
PYTHONPATH=server:server/tests PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_combat_abandon test_combat_results test_combat_lifecycle -q
```

## Casos específicos que deben añadirse o reproducirse

| Caso | Acción | Resultado exigido | Estado |
| --- | --- | --- | --- |
| Flag 0 real | Abandono autorizado con frameobservado | Cleanup correcto o respuesta compatible, sin fightresidual | Pendiente de implementar/verificar |
| IDajeno | Continuation de otro fight | Rechazo sin liberar reservas | Pendiente de implementar/verificar |
| Duplicado | 13952/12925 repetidos | HP/release una vez y no rewards | Pendiente de implementar/verificar |
| ACKpendiente | Abandonar durante acción | Pendientes terminados y control restaurado | Pendiente de implementar/verificar |
| Sincontinuation | Corte trascleanup | Recovery termina sin bloqueo eterno | Pendiente de implementar/verificar |
| Nuevofight/zaap | Acción trasretorno | Disponibles; captura verifica ambos handlers | Pendiente de implementar/verificar |

## Método y criterios

Usar personaje y almacenamiento de prueba aislados. Registrar identidad de instancia, versión, estado inicial, petición, respuesta decodificada y estado durable final. Controlar reloj y RNG en los casos deterministas. Ejecutar límites de ownership, sesión obsoleta, índices/UID inválidos y payload truncado donde apliquen.

Repetir operaciones confirmadas y cortes alrededor del commit/ACK; ninguna repetición puede duplicar consumo, recompensa o efectos. Verificar observadores y reconexión cuando el caso sea multijugador. La prueba gráfica confirma integración, mientras la fixture de protocolo debe fallar si cambian layout o semántica.

Invariante: Abandonar no concede XP/kamas/drop; toda reserva y referencia de sesión quedan liberadas una vez.

Registrar cada caso como PASS, FAIL o NO EJECUTADO, con evidencia. No convertir una omisión, un click optimista o un resultado de otro snapshot en PASS.
