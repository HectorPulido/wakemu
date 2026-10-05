# Pruebas y aceptación — 17

## Base existente

- [test_aptitudes.py](../../../server/tests/test_aptitudes.py): incluido en la ejecución de base registrada.
- [test_builds.py](../../../server/tests/test_builds.py): incluido en la ejecución de base registrada.
- [test_ring_build_integration.py](../../../server/tests/test_ring_build_integration.py): referencia existente; no ejecutado en el lote de base registrado.

El lote común descubrió **133 tests: 123 pasaron y 10 se omitieron** (Redis real); salida 0. No implica que todas las pruebas relacionadas de esta carpeta se ejecutaran, ni que los casos nuevos pasen. Ver [VALIDACION.md](../VALIDACION.md).

Comando dirigido propuesto, desde la raíz y en entorno autorizado:

```sh
PYTHONPATH=server:server/tests PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_aptitudes test_builds test_ring_build_integration -q
```

## Casos específicos que deben añadirse o reproducirse

| Caso | Acción | Resultado exigido | Estado |
| --- | --- | --- | --- |
| A→B→A | Subir y retirar mismo punto con equipo fijo | StatsA final=StatsA inicial exactamente | Pendiente de implementar/verificar |
| Guardar idéntico 10 veces | Misma hoja y revision controlada | Ningún bonus acumulado | Pendiente de implementar/verificar |
| Presupuesto excedido | Un punto sobre categoría | Rechazo y hoja anterior intacta | Pendiente de implementar/verificar |
| HP parcial | Cambiar máximo con HP50% | Regla estable; no cura por editar | Pendiente de implementar/verificar |
| Build secundaria | Aptitudes distintas en 1/2 | Solo activa contribuye una vez | Pendiente de implementar/verificar |
| Reconexion/flush | Recargar hoja canónica | Mismas stats que en vivo | Pendiente de implementar/verificar |

## Método y criterios

Usar personaje y almacenamiento de prueba aislados. Registrar identidad de instancia, versión, estado inicial, petición, respuesta decodificada y estado durable final. Controlar reloj y RNG en los casos deterministas. Ejecutar límites de ownership, sesión obsoleta, índices/UID inválidos y payload truncado donde apliquen.

Repetir operaciones confirmadas y cortes alrededor del commit/ACK; ninguna repetición puede duplicar consumo, recompensa o efectos. Verificar observadores y reconexión cuando el caso sea multijugador. La prueba gráfica confirma integración, mientras la fixture de protocolo debe fallar si cambian layout o semántica.

Invariante: Mismo estado produce mismas estadísticas; volver a una hoja previa revierte bonus sin borrar daño real.

Registrar cada caso como PASS, FAIL o NO EJECUTADO, con evidencia. No convertir una omisión, un click optimista o un resultado de otro snapshot en PASS.
