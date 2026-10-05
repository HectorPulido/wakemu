# Pruebas y aceptación — 26

## Base existente

- [test_haven_bag_store.py](../../../server/tests/test_haven_bag_store.py): incluido en la ejecución de base registrada.
- [test_haven_bag.py](../../../server/tests/test_haven_bag.py): incluido en la ejecución de base registrada.
- [test_inventory_move.py](../../../server/tests/test_inventory_move.py): incluido en la ejecución de base registrada.

El lote común descubrió **133 tests: 123 pasaron y 10 se omitieron** (Redis real); salida 0. No implica que todas las pruebas relacionadas de esta carpeta se ejecutaran, ni que los casos nuevos pasen. Ver [VALIDACION.md](../VALIDACION.md).

Comando dirigido propuesto, desde la raíz y en entorno autorizado:

```sh
PYTHONPATH=server:server/tests PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_haven_bag_store test_haven_bag test_inventory_move -q
```

## Casos específicos que deben añadirse o reproducirse

| Caso | Acción | Resultado exigido | Estado |
| --- | --- | --- | --- |
| Inserción | UIDgemapropia y ranura compatible | Una sala habilitada y unidad retirada del inventario | Pendiente de implementar/verificar |
| Stack 3 | Instalar una de tres | Resto 2 y un UIDinstalado | Pendiente de implementar/verificar |
| Retirada llena | Sin slot en bolsillo | Rechazo sin pérdida de sala/gema | Pendiente de implementar/verificar |
| Sala ocupada | Muebles/otro jugador dentro | Regla segura, sin borrar bienes | Pendiente de implementar/verificar |
| UID duplicado | Misma gema a dos slots | Rechazo de segunda transición | Pendiente de implementar/verificar |
| Reconnect | Salir/volver y reloadDB | Mismo layout/UID/ACL | Pendiente de implementar/verificar |

## Método y criterios

Usar personaje y almacenamiento de prueba aislados. Registrar identidad de instancia, versión, estado inicial, petición, respuesta decodificada y estado durable final. Controlar reloj y RNG en los casos deterministas. Ejecutar límites de ownership, sesión obsoleta, índices/UID inválidos y payload truncado donde apliquen.

Repetir operaciones confirmadas y cortes alrededor del commit/ACK; ninguna repetición puede duplicar consumo, recompensa o efectos. Verificar observadores y reconexión cuando el caso sea multijugador. La prueba gráfica confirma integración, mientras la fixture de protocolo debe fallar si cambian layout o semántica.

Invariante: Una UID está en inventario o slot, nunca ambos; retirada no elimina contenido ni concede gema nueva.

Registrar cada caso como PASS, FAIL o NO EJECUTADO, con evidencia. No convertir una omisión, un click optimista o un resultado de otro snapshot en PASS.
