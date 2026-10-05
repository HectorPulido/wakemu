# Pruebas y aceptación — 27

## Base existente

- [test_planting_context.py](../../../server/tests/test_planting_context.py): incluido en la ejecución de base registrada.

El lote común descubrió **133 tests: 123 pasaron y 10 se omitieron** (Redis real); salida 0. No implica que todas las pruebas relacionadas de esta carpeta se ejecutaran, ni que los casos nuevos pasen. Ver [VALIDACION.md](../VALIDACION.md).

Comando dirigido propuesto, desde la raíz y en entorno autorizado:

```sh
PYTHONPATH=server:server/tests PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_planting_context -q
```

## Casos específicos que deben añadirse o reproducirse

| Caso | Acción | Resultado exigido | Estado |
| --- | --- | --- | --- |
| Dos jugadores | Misma zona | Estado/climate_revision idénticos | Pendiente de implementar/verificar |
| Cambio controlado | Reloj y RNG fijo | Un estado y actualización compatibles | Pendiente de implementar/verificar |
| Cron repetido | Mismo event_id | Sin segunda transición | Pendiente de implementar/verificar |
| Zona vacía | Sin presencia | Semántica reloj acordada y sin simulación prohibida | Pendiente de implementar/verificar |
| Plantación | Intento antes/después de clima | Probabilidad usa revisión correcta | Pendiente de implementar/verificar |
| Recovery | Reabrir estado | Mismo clima/calendario, no nuevo sorteo | Pendiente de implementar/verificar |

## Método y criterios

Usar personaje y almacenamiento de prueba aislados. Registrar identidad de instancia, versión, estado inicial, petición, respuesta decodificada y estado durable final. Controlar reloj y RNG en los casos deterministas. Ejecutar límites de ownership, sesión obsoleta, índices/UID inválidos y payload truncado donde apliquen.

Repetir operaciones confirmadas y cortes alrededor del commit/ACK; ninguna repetición puede duplicar consumo, recompensa o efectos. Verificar observadores y reconexión cuando el caso sea multijugador. La prueba gráfica confirma integración, mientras la fixture de protocolo debe fallar si cambian layout o semántica.

Invariante: Clima de una zona es compartido, versionado y no recalculado por jugador.

Registrar cada caso como PASS, FAIL o NO EJECUTADO, con evidencia. No convertir una omisión, un click optimista o un resultado de otro snapshot en PASS.
