# Pruebas y aceptación — 1

## Base existente

- [test_planting.py](../../../server/tests/test_planting.py): incluido en la ejecución de base registrada.
- [test_planting_runtime.py](../../../server/tests/test_planting_runtime.py): incluido en la ejecución de base registrada.

El lote común descubrió **133 tests: 123 pasaron y 10 se omitieron** (Redis real); salida 0. No implica que todas las pruebas relacionadas de esta carpeta se ejecutaran, ni que los casos nuevos pasen. Ver [VALIDACION.md](../VALIDACION.md).

Comando dirigido propuesto, desde la raíz y en entorno autorizado:

```sh
PYTHONPATH=server:server/tests PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_planting test_planting_runtime -q
```

## Casos específicos que deben añadirse o reproducirse

| Caso | Acción | Resultado exigido | Estado |
| --- | --- | --- | --- |
| Stack 5 | Plantar una vez, leer antes/después y reconectar | Cantidad 4 en vivo y persistida; un recurso | Pendiente de implementar/verificar |
| Última semilla | Plantar con cantidad 1 | Ítem desaparece correctamente; no stack 0 | Pendiente de implementar/verificar |
| Reintento | Repetir mismo completado confirmado | Un descuento y un recurso total | Pendiente de implementar/verificar |
| Cancelar | Reservar acción y cancelarla antes del commit | Sin recurso ni descuento según contrato | Pendiente de implementar/verificar |
| Competencia por celda | Dos actores completan para la misma celda | Solo una reserva/commit gana; perdedor conserva semilla según política | Pendiente de implementar/verificar |
| Corte tras commit | Desconectar después de confirmar antes de notificar | Recuperación muestra cantidad correcta, sin nuevo descuento | Pendiente de implementar/verificar |

## Método y criterios

Usar personaje y almacenamiento de prueba aislados. Registrar identidad de instancia, versión, estado inicial, petición, respuesta decodificada y estado durable final. Controlar reloj y RNG en los casos deterministas. Ejecutar límites de ownership, sesión obsoleta, índices/UID inválidos y payload truncado donde apliquen.

Repetir operaciones confirmadas y cortes alrededor del commit/ACK; ninguna repetición puede duplicar consumo, recompensa o efectos. Verificar observadores y reconexión cuando el caso sea multijugador. La prueba gráfica confirma integración, mientras la fixture de protocolo debe fallar si cambian layout o semántica.

Invariante: cantidad_antes = cantidad_después + consumo_confirmado; nunca dos consumos por un resultado repetido.

Registrar cada caso como PASS, FAIL o NO EJECUTADO, con evidencia. No convertir una omisión, un click optimista o un resultado de otro snapshot en PASS.
