# Pruebas y aceptación — 10

## Base existente

- [test_combat_rewards.py](../../../server/tests/test_combat_rewards.py): incluido en la ejecución de base registrada.
- [test_inventory_uids.py](../../../server/tests/test_inventory_uids.py): referencia existente; no ejecutado en el lote de base registrado.

El lote común descubrió **133 tests: 123 pasaron y 10 se omitieron** (Redis real); salida 0. No implica que todas las pruebas relacionadas de esta carpeta se ejecutaran, ni que los casos nuevos pasen. Ver [VALIDACION.md](../VALIDACION.md).

Comando dirigido propuesto, desde la raíz y en entorno autorizado:

```sh
PYTHONPATH=server:server/tests PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_combat_rewards test_inventory_uids -q
```

## Casos específicos que deben añadirse o reproducirse

| Caso | Acción | Resultado exigido | Estado |
| --- | --- | --- | --- |
| Victoria con tabla | RNG fijo para uno y cero drops | Lista exacta del recibo | Pendiente de implementar/verificar |
| Probabilidad saturada | Multiplicador lleva p>1 | Clamp documentado, no drops infinitos | Pendiente de implementar/verificar |
| Inventario lleno | No hay slot para premio | Entrega pendiente durable o regla explícita, sin pérdida | Pendiente de implementar/verificar |
| Wallet cerca de límite | Kamas grandes | Rechazo/clamp según contrato sin overflow | Pendiente de implementar/verificar |
| Resultado duplicado | Repetir premio de mismo fight | Sin nuevos UIDs ni kamas | Pendiente de implementar/verificar |
| Corte tras commit | Recovery antes de respuesta | Resumen e inventario mismo premio | Pendiente de implementar/verificar |

## Método y criterios

Usar personaje y almacenamiento de prueba aislados. Registrar identidad de instancia, versión, estado inicial, petición, respuesta decodificada y estado durable final. Controlar reloj y RNG en los casos deterministas. Ejecutar límites de ownership, sesión obsoleta, índices/UID inválidos y payload truncado donde apliquen.

Repetir operaciones confirmadas y cortes alrededor del commit/ACK; ninguna repetición puede duplicar consumo, recompensa o efectos. Verificar observadores y reconexión cuando el caso sea multijugador. La prueba gráfica confirma integración, mientras la fixture de protocolo debe fallar si cambian layout o semántica.

Invariante: Resumen=recibo=wallet/inventario; cada UID otorgado y cada kama se entregan una vez.

Registrar cada caso como PASS, FAIL o NO EJECUTADO, con evidencia. No convertir una omisión, un click optimista o un resultado de otro snapshot en PASS.
