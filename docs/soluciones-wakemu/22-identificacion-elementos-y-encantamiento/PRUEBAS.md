# Pruebas y aceptación — 22

## Base existente

- [test_inventory_elements.py](../../../server/tests/test_inventory_elements.py): incluido en la ejecución de base registrada.
- [test_inventory_actions.py](../../../server/tests/test_inventory_actions.py): referencia existente; no ejecutado en el lote de base registrado.
- [test_inventory_move.py](../../../server/tests/test_inventory_move.py): incluido en la ejecución de base registrada.
- [test_ring_build_integration.py](../../../server/tests/test_ring_build_integration.py): referencia existente; no ejecutado en el lote de base registrado.

El lote común descubrió **133 tests: 123 pasaron y 10 se omitieron** (Redis real); salida 0. No implica que todas las pruebas relacionadas de esta carpeta se ejecutaran, ni que los casos nuevos pasen. Ver [VALIDACION.md](../VALIDACION.md).

Comando dirigido propuesto, desde la raíz y en entorno autorizado:

```sh
PYTHONPATH=server:server/tests PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_inventory_elements test_inventory_actions test_inventory_move test_ring_build_integration -q
```

## Casos específicos que deben añadirse o reproducirse

| Caso | Acción | Resultado exigido | Estado |
| --- | --- | --- | --- |
| Identificar por primera vez | UID legacy propio con cantidad 1 | Una selección/sorteo persistidos y tooltip coherente | Pendiente de implementar/verificar |
| Doble clic/retry | Repetir confirmación o reconnect | No reroll, consumo o sockets adicionales | Pendiente de implementar/verificar |
| Stack individual | Identificar una unidad de stack 3 | Una instancia independiente y dos restantes; suma 3 | Pendiente de implementar/verificar |
| Reasignar elementos | Cambiar elección con objeto equipado | Solo elementos elegidos aplicados una vez | Pendiente de implementar/verificar |
| Reciclar/sacrificar | Intento legal y retry tras commit | Consumo 1 y producto/cargas una vez | Pendiente de implementar/verificar |
| Sublimación válida/inválida | Orden compatible e incompatible | Solo válida consume/aplica; inválida conserva scroll | Pendiente de implementar/verificar |
| Retirar efecto | Inversión conocida y retirada repetida | Refund según fórmula una sola vez | Pendiente de implementar/verificar |
| Recovery/transfer | Flush, mover dueño y recargar | Propiedades/UID/inversión conservados, no rerolled | Pendiente de implementar/verificar |

## Método y criterios

Usar personaje y almacenamiento de prueba aislados. Registrar identidad de instancia, versión, estado inicial, petición, respuesta decodificada y estado durable final. Controlar reloj y RNG en los casos deterministas. Ejecutar límites de ownership, sesión obsoleta, índices/UID inválidos y payload truncado donde apliquen.

Repetir operaciones confirmadas y cortes alrededor del commit/ACK; ninguna repetición puede duplicar consumo, recompensa o efectos. Verificar observadores y reconexión cuando el caso sea multijugador. La prueba gráfica confirma integración, mientras la fixture de protocolo debe fallar si cambian layout o semántica.

Invariante: Propiedades pertenecen a una unidad; reintento no vuelve a sortear; consumo/reembolso y modificación se confirman juntos.

Registrar cada caso como PASS, FAIL o NO EJECUTADO, con evidencia. No convertir una omisión, un click optimista o un resultado de otro snapshot en PASS.
