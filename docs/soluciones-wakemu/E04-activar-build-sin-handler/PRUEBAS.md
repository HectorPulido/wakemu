# Pruebas y aceptación — E04

## Base existente

- [test_builds.py](../../../server/tests/test_builds.py): incluido en la ejecución de base registrada.
- [test_ring_build_integration.py](../../../server/tests/test_ring_build_integration.py): referencia existente; no ejecutado en el lote de base registrado.

El lote común descubrió **133 tests: 123 pasaron y 10 se omitieron** (Redis real); salida 0. No implica que todas las pruebas relacionadas de esta carpeta se ejecutaran, ni que los casos nuevos pasen. Ver [VALIDACION.md](../VALIDACION.md).

Comando dirigido propuesto, desde la raíz y en entorno autorizado:

```sh
PYTHONPATH=server:server/tests PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_builds test_ring_build_integration -q
```

## Casos específicos que deben añadirse o reproducirse

| Caso | Acción | Resultado exigido | Estado |
| --- | --- | --- | --- |
| Petición real | Activar índice 1 | Handler y selección autoritativa | Pendiente de implementar/verificar |
| Identidad ajena | Enviar ID de otro personaje | Rechazo sin mutación | Pendiente de implementar/verificar |
| Índice ausente | Solicitar hoja inexistente | Rechazo y controles restaurados | Pendiente de implementar/verificar |
| Combate | Activar durante turno | Política explícita y snapshot coherente | Pendiente de implementar/verificar |
| Repetición | Reenviar misma operación | Sin curación o bonus doble | Pendiente de implementar/verificar |
| Desconexión | Cortar después de commit | Selección recuperada | Pendiente de implementar/verificar |

## Método y criterios

Usar personaje y almacenamiento de prueba aislados. Registrar identidad de instancia, versión, estado inicial, petición, respuesta decodificada y estado durable final. Controlar reloj y RNG en los casos deterministas. Ejecutar límites de ownership, sesión obsoleta, índices/UID inválidos y payload truncado donde apliquen.

Repetir operaciones confirmadas y cortes alrededor del commit/ACK; ninguna repetición puede duplicar consumo, recompensa o efectos. Verificar observadores y reconexión cuando el caso sea multijugador. La prueba gráfica confirma integración, mientras la fixture de protocolo debe fallar si cambian layout o semántica.

Invariante: El check optimista del cliente se confirma por servidor o se revierte con un mensaje probado.

Registrar cada caso como PASS, FAIL o NO EJECUTADO, con evidencia. No convertir una omisión, un click optimista o un resultado de otro snapshot en PASS.
