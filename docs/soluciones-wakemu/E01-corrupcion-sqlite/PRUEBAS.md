# Pruebas y aceptación — E01

## Base existente

- [test_build_journal.py](../../../server/tests/test_build_journal.py): incluido en la ejecución de base registrada.
- [test_planting_runtime.py](../../../server/tests/test_planting_runtime.py): incluido en la ejecución de base registrada.

El lote común descubrió **133 tests: 123 pasaron y 10 se omitieron** (Redis real); salida 0. No implica que todas las pruebas relacionadas de esta carpeta se ejecutaran, ni que los casos nuevos pasen. Ver [VALIDACION.md](../VALIDACION.md).

Comando dirigido propuesto, desde la raíz y en entorno autorizado:

```sh
PYTHONPATH=server:server/tests PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_build_journal test_planting_runtime -q
```

## Casos específicos que deben añadirse o reproducirse

| Caso | Acción | Resultado exigido | Estado |
| --- | --- | --- | --- |
| Backup concurrente | Fixturetemporal conWAL ywrites | Backup íntegro concommits esperados | Pendiente de implementar/verificar |
| Integridad | Copiaverificada | quick/integrity/foreignkeys sinerror o detalle claro | Pendiente de implementar/verificar |
| ReconciliarRedis | Baseline anterior/nuevo | Sin replay sobre SQL incompatible | Pendiente de implementar/verificar |
| Objeto duplicado | Copias conUID/recibo repetidos | Validación detecta antes de cutover | Pendiente de implementar/verificar |
| Planta recuperada | Timer/resource de copia sana | Etapas pueden avanzar sinmalformed | Pendiente de implementar/verificar |
| Rollback | Ensayo autorizado sobre copia | Restore reproduceestado conocido, no datos mezclados | Pendiente de implementar/verificar |

## Método y criterios

Usar personaje y almacenamiento de prueba aislados. Registrar identidad de instancia, versión, estado inicial, petición, respuesta decodificada y estado durable final. Controlar reloj y RNG en los casos deterministas. Ejecutar límites de ownership, sesión obsoleta, índices/UID inválidos y payload truncado donde apliquen.

Repetir operaciones confirmadas y cortes alrededor del commit/ACK; ninguna repetición puede duplicar consumo, recompensa o efectos. Verificar observadores y reconexión cuando el caso sea multijugador. La prueba gráfica confirma integración, mientras la fixture de protocolo debe fallar si cambian layout o semántica.

Invariante: Recovery nunca inventa objetos/progreso; la copia reparada se valida antes de sustituir la autoridad.

Registrar cada caso como PASS, FAIL o NO EJECUTADO, con evidencia. No convertir una omisión, un click optimista o un resultado de otro snapshot en PASS.
