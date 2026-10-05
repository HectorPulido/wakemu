# Pruebas y aceptación — 4

## Base existente

- [test_planting.py](../../../server/tests/test_planting.py): incluido en la ejecución de base registrada.
- [test_planting_context.py](../../../server/tests/test_planting_context.py): incluido en la ejecución de base registrada.

El lote común descubrió **133 tests: 123 pasaron y 10 se omitieron** (Redis real); salida 0. No implica que todas las pruebas relacionadas de esta carpeta se ejecutaran, ni que los casos nuevos pasen. Ver [VALIDACION.md](../VALIDACION.md).

Comando dirigido propuesto, desde la raíz y en entorno autorizado:

```sh
PYTHONPATH=server:server/tests PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_planting test_planting_context -q
```

## Casos específicos que deben añadirse o reproducirse

| Caso | Acción | Resultado exigido | Estado |
| --- | --- | --- | --- |
| 0% | RNG favorable, celda válida | Siempre falla por tirada; sin recurso | Pendiente de implementar/verificar |
| 100% | RNG en extremo superior | Siempre éxito si validaciones pasan | Pendiente de implementar/verificar |
| 1% frontera | Draw justo antes/en el umbral | Condición y escala sin error de factor 100 | Pendiente de implementar/verificar |
| 10.000 tiradas | Generador independiente fijo, p=0,01 | Resultado evaluado con intervalo binomial, no exigir exactamente 100 | Pendiente de implementar/verificar |
| Retry mismo intento | Duplicar completado tras fallo | Mismo resultado, no otra tirada | Pendiente de implementar/verificar |
| Cambio climático | Clima cambia tras iniciar | Semántica de snapshot documentada y resultado coherente | Pendiente de implementar/verificar |

## Método y criterios

Usar personaje y almacenamiento de prueba aislados. Registrar identidad de instancia, versión, estado inicial, petición, respuesta decodificada y estado durable final. Controlar reloj y RNG en los casos deterministas. Ejecutar límites de ownership, sesión obsoleta, índices/UID inválidos y payload truncado donde apliquen.

Repetir operaciones confirmadas y cortes alrededor del commit/ACK; ninguna repetición puede duplicar consumo, recompensa o efectos. Verificar observadores y reconexión cuando el caso sea multijugador. La prueba gráfica confirma integración, mientras la fixture de protocolo debe fallar si cambian layout o semántica.

Invariante: Permiso no equivale a probabilidad; repetir una solicitud no vuelve a sortear el resultado.

Registrar cada caso como PASS, FAIL o NO EJECUTADO, con evidencia. No convertir una omisión, un click optimista o un resultado de otro snapshot en PASS.
