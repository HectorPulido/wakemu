# Pruebas y aceptación — 30

## Base existente

- [test_profession_store.py](../../../server/tests/test_profession_store.py): incluido en la ejecución de base registrada.
- [test_haven_bag_store.py](../../../server/tests/test_haven_bag_store.py): incluido en la ejecución de base registrada.
- [test_inventory_actions.py](../../../server/tests/test_inventory_actions.py): referencia existente; no ejecutado en el lote de base registrado.

El lote común descubrió **133 tests: 123 pasaron y 10 se omitieron** (Redis real); salida 0. No implica que todas las pruebas relacionadas de esta carpeta se ejecutaran, ni que los casos nuevos pasen. Ver [VALIDACION.md](../VALIDACION.md).

Comando dirigido propuesto, desde la raíz y en entorno autorizado:

```sh
PYTHONPATH=server:server/tests PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_profession_store test_haven_bag_store test_inventory_actions -q
```

## Casos específicos que deben añadirse o reproducirse

| Caso | Acción | Resultado exigido | Estado |
| --- | --- | --- | --- |
| Presencia | Dos clientes entran mapa | Misma entidad visible y posición real | Pendiente de implementar/verificar |
| Receta válida | Materiales suficientes, cantidad 1 | Consumo/producto/XP exactos | Pendiente de implementar/verificar |
| Material insuficiente | Falta una unidad | No consumo parcial | Pendiente de implementar/verificar |
| Inventario lleno | Producto no cabe | Rechazo/entrega definida sin pérdida | Pendiente de implementar/verificar |
| Retry crafting | Repetir operation_id | Un producto/XP total | Pendiente de implementar/verificar |
| Mesa portátil | Dueño/visitante segúnACL | Permisos y resultado coherentes | Pendiente de implementar/verificar |

## Método y criterios

Usar personaje y almacenamiento de prueba aislados. Registrar identidad de instancia, versión, estado inicial, petición, respuesta decodificada y estado durable final. Controlar reloj y RNG en los casos deterministas. Ejecutar límites de ownership, sesión obsoleta, índices/UID inválidos y payload truncado donde apliquen.

Repetir operaciones confirmadas y cortes alrededor del commit/ACK; ninguna repetición puede duplicar consumo, recompensa o efectos. Verificar observadores y reconexión cuando el caso sea multijugador. La prueba gráfica confirma integración, mientras la fixture de protocolo debe fallar si cambian layout o semántica.

Invariante: Ver mesa no acredita crafting; cada receta conserva materiales y concede resultado/XP una vez.

Registrar cada caso como PASS, FAIL o NO EJECUTADO, con evidencia. No convertir una omisión, un click optimista o un resultado de otro snapshot en PASS.
