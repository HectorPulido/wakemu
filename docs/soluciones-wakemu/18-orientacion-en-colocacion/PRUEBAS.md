# Pruebas y aceptación — 18

## Base existente

- [test_combat_orientation.py](../../../server/tests/test_combat_orientation.py): incluido en la ejecución de base registrada.
- [test_combat_displacement_facing.py](../../../server/tests/test_combat_displacement_facing.py): referencia existente; no ejecutado en el lote de base registrado.

El lote común descubrió **133 tests: 123 pasaron y 10 se omitieron** (Redis real); salida 0. No implica que todas las pruebas relacionadas de esta carpeta se ejecutaran, ni que los casos nuevos pasen. Ver [VALIDACION.md](../VALIDACION.md).

Comando dirigido propuesto, desde la raíz y en entorno autorizado:

```sh
PYTHONPATH=server:server/tests PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_combat_orientation test_combat_displacement_facing -q
```

## Casos específicos que deben añadirse o reproducirse

| Caso | Acción | Resultado exigido | Estado |
| --- | --- | --- | --- |
| Cuatro cardinales | Cambiar antes de ready | Dirección visible y costo 0 | Pendiente de implementar/verificar |
| Actor ajeno | CuentaA orienta actorB | Rechazo sin mutación | Pendiente de implementar/verificar |
| Ready concurrente | Enviar orientación al cerrar placement | Orden/rechazo coherente por revisión | Pendiente de implementar/verificar |
| Inicio | Comenzar tras dirección elegida | Facing conservado | Pendiente de implementar/verificar |
| Reconnect | Volver durante placement | Misma dirección | Pendiente de implementar/verificar |
| Fase active | Girar fuera de turno/ACK pendiente | Restricciones actuales mantenidas | Pendiente de implementar/verificar |

## Método y criterios

Usar personaje y almacenamiento de prueba aislados. Registrar identidad de instancia, versión, estado inicial, petición, respuesta decodificada y estado durable final. Controlar reloj y RNG en los casos deterministas. Ejecutar límites de ownership, sesión obsoleta, índices/UID inválidos y payload truncado donde apliquen.

Repetir operaciones confirmadas y cortes alrededor del commit/ACK; ninguna repetición puede duplicar consumo, recompensa o efectos. Verificar observadores y reconexión cuando el caso sea multijugador. La prueba gráfica confirma integración, mientras la fixture de protocolo debe fallar si cambian layout o semántica.

Invariante: Girar en colocación cambia solo facing de actor propio y no debita AP/MP ni inicia un turno.

Registrar cada caso como PASS, FAIL o NO EJECUTADO, con evidencia. No convertir una omisión, un click optimista o un resultado de otro snapshot en PASS.
