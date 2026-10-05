# Pruebas y aceptación — 23

## Base existente

- [test_inventory_bags.py](../../../server/tests/test_inventory_bags.py): incluido en la ejecución de base registrada.
- [test_inventory_move.py](../../../server/tests/test_inventory_move.py): incluido en la ejecución de base registrada.
- [test_inventory_uids.py](../../../server/tests/test_inventory_uids.py): referencia existente; no ejecutado en el lote de base registrado.

El lote común descubrió **133 tests: 123 pasaron y 10 se omitieron** (Redis real); salida 0. No implica que todas las pruebas relacionadas de esta carpeta se ejecutaran, ni que los casos nuevos pasen. Ver [VALIDACION.md](../VALIDACION.md).

Comando dirigido propuesto, desde la raíz y en entorno autorizado:

```sh
PYTHONPATH=server:server/tests PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_inventory_bags test_inventory_move test_inventory_uids -q
```

## Casos específicos que deben añadirse o reproducirse

| Caso | Acción | Resultado exigido | Estado |
| --- | --- | --- | --- |
| Stack 3 legal | Equipar una unidad | Dos originales + una equipada, capacidad real y mapa visible | Pendiente de implementar/verificar |
| Specialized no soportado | Criterios sin implementar | Rechazo seguro, quantity 3 y UI estable | Pendiente de implementar/verificar |
| Slot ocupado | Otro bolso con contenido | Cambio legal o rechazo total, sin perder contenido | Pendiente de implementar/verificar |
| Sin espacio/splitfallo | UID/capacidad no disponibles | Rollback íntegro | Pendiente de implementar/verificar |
| 13713 parser | Decodificar respuesta de rechazo nativamente | Entidad/codec correcto sin underflow/XP absurdo | Pendiente de implementar/verificar |
| Retry/reconnect | Repetir petición y volver | No dos bolsos ni pérdida de unidad | Pendiente de implementar/verificar |

## Método y criterios

Usar personaje y almacenamiento de prueba aislados. Registrar identidad de instancia, versión, estado inicial, petición, respuesta decodificada y estado durable final. Controlar reloj y RNG en los casos deterministas. Ejecutar límites de ownership, sesión obsoleta, índices/UID inválidos y payload truncado donde apliquen.

Repetir operaciones confirmadas y cortes alrededor del commit/ACK; ninguna repetición puede duplicar consumo, recompensa o efectos. Verificar observadores y reconexión cuando el caso sea multijugador. La prueba gráfica confirma integración, mientras la fixture de protocolo debe fallar si cambian layout o semántica.

Invariante: La suma de unidades se conserva; ningún rechazo genera mapa negro ni características absurdas.

Registrar cada caso como PASS, FAIL o NO EJECUTADO, con evidencia. No convertir una omisión, un click optimista o un resultado de otro snapshot en PASS.
