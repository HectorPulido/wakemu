# Pruebas y aceptación — E02

## Base existente

- [test_inventory_move.py](../../../server/tests/test_inventory_move.py): incluido en la ejecución de base registrada.
- [test_inventory_bags.py](../../../server/tests/test_inventory_bags.py): incluido en la ejecución de base registrada.

El lote común descubrió **133 tests: 123 pasaron y 10 se omitieron** (Redis real); salida 0. No implica que todas las pruebas relacionadas de esta carpeta se ejecutaran, ni que los casos nuevos pasen. Ver [VALIDACION.md](../VALIDACION.md).

Comando dirigido propuesto, desde la raíz y en entorno autorizado:

```sh
PYTHONPATH=server:server/tests PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_inventory_move test_inventory_bags -q
```

## Casos específicos que deben añadirse o reproducirse

| Caso | Acción | Resultado exigido | Estado |
| --- | --- | --- | --- |
| Parseractual | Payload de bolsas interpretado como entidad | Reproducefallo; fijar una fixture defectuosa | Pendiente de implementar/verificar |
| Parserpropuesto | Carriercompleto/específico | Decodifica todo sinunderflow | Pendiente de implementar/verificar |
| Rechazobolso | Stack 3 nosupported | UIestable yquantity 3 | Pendiente de implementar/verificar |
| Rechazotransfer | Slotfuera/lleno | Rollbackcanónico sinmapanegro | Pendiente de implementar/verificar |
| Propiedadesricas | Items de 22 ybuilds | Sinperder máscaras/engastes | Pendiente de implementar/verificar |
| Mismorechazo 2 veces | Retry sinmutación | Stats/inventory idénticos | Pendiente de implementar/verificar |

## Método y criterios

Usar personaje y almacenamiento de prueba aislados. Registrar identidad de instancia, versión, estado inicial, petición, respuesta decodificada y estado durable final. Controlar reloj y RNG en los casos deterministas. Ejecutar límites de ownership, sesión obsoleta, índices/UID inválidos y payload truncado donde apliquen.

Repetir operaciones confirmadas y cortes alrededor del commit/ACK; ninguna repetición puede duplicar consumo, recompensa o efectos. Verificar observadores y reconexión cuando el caso sea multijugador. La prueba gráfica confirma integración, mientras la fixture de protocolo debe fallar si cambian layout o semántica.

Invariante: Toda respuesta se valida por su parser nativo; un rechazo no altera el estado visual de otros dominios.

Registrar cada caso como PASS, FAIL o NO EJECUTADO, con evidencia. No convertir una omisión, un click optimista o un resultado de otro snapshot en PASS.
