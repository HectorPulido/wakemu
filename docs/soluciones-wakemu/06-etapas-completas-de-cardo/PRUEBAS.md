# Pruebas y aceptación — 6

## Base existente

- [test_planting_runtime.py](../../../server/tests/test_planting_runtime.py): incluido en la ejecución de base registrada.
- [test_planting.py](../../../server/tests/test_planting.py): incluido en la ejecución de base registrada.

El lote común descubrió **133 tests: 123 pasaron y 10 se omitieron** (Redis real); salida 0. No implica que todas las pruebas relacionadas de esta carpeta se ejecutaran, ni que los casos nuevos pasen. Ver [VALIDACION.md](../VALIDACION.md).

Comando dirigido propuesto, desde la raíz y en entorno autorizado:

```sh
PYTHONPATH=server:server/tests PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_planting_runtime test_planting -q
```

## Casos específicos que deben añadirse o reproducirse

| Caso | Acción | Resultado exigido | Estado |
| --- | --- | --- | --- |
| Cadena Cardo | Reloj avanza por cada plazo | Todas las etapas catalogadas, incluidas final/cosechable | Pendiente de implementar/verificar |
| Etapas no contiguas | Fixture con ids 1,4,9 | Transiciones del grafo, nunca +1 ciego | Pendiente de implementar/verificar |
| Cosecha concurrente | Cosechar mientras vence timer | No planta resucitada ni producto duplicado | Pendiente de implementar/verificar |
| Tick duplicado | Misma revisión vencida dos veces | Una transición aplicada | Pendiente de implementar/verificar |
| Zona sin jugadores | Tiempo externo sigue avanzando | Reloj de recurso respeta pausa acordada | Pendiente de implementar/verificar |
| Recovery | Guardar y reabrir en etapa intermedia | Conserva etapa y próximo cambio | Pendiente de implementar/verificar |

## Método y criterios

Usar personaje y almacenamiento de prueba aislados. Registrar identidad de instancia, versión, estado inicial, petición, respuesta decodificada y estado durable final. Controlar reloj y RNG en los casos deterministas. Ejecutar límites de ownership, sesión obsoleta, índices/UID inválidos y payload truncado donde apliquen.

Repetir operaciones confirmadas y cortes alrededor del commit/ACK; ninguna repetición puede duplicar consumo, recompensa o efectos. Verificar observadores y reconexión cuando el caso sea multijugador. La prueba gráfica confirma integración, mientras la fixture de protocolo debe fallar si cambian layout o semántica.

Invariante: Solo crece un recurso existente por una arista legal; un temporizador antiguo no recrea lo cosechado.

Registrar cada caso como PASS, FAIL o NO EJECUTADO, con evidencia. No convertir una omisión, un click optimista o un resultado de otro snapshot en PASS.
