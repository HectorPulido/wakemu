# Pruebas y aceptación — E10

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
| Conjunto 0→0,2 | Añadir nueva secundaria | Parser resuelve 2 sin perder 0 | Pendiente de implementar/verificar |
| Update existente | Cambiar equipo 0 | No cambia cardinalidad indebidamente | Pendiente de implementar/verificar |
| ACK ybootstrap | Comparar después de guardar | Índices/hojas equivalentes | Pendiente de implementar/verificar |
| Duplicateupdate | Repetir payload | Una entrada por índice | Pendiente de implementar/verificar |
| Fallo save | Ítem ajeno | Conjunto anterior intacto | Pendiente de implementar/verificar |
| Crear en UI | Nueva fila y Equipables | Modelo existente sin modelo nulo | Pendiente de implementar/verificar |

## Método y criterios

Usar personaje y almacenamiento de prueba aislados. Registrar identidad de instancia, versión, estado inicial, petición, respuesta decodificada y estado durable final. Controlar reloj y RNG en los casos deterministas. Ejecutar límites de ownership, sesión obsoleta, índices/UID inválidos y payload truncado donde apliquen.

Repetir operaciones confirmadas y cortes alrededor del commit/ACK; ninguna repetición puede duplicar consumo, recompensa o efectos. Verificar observadores y reconexión cuando el caso sea multijugador. La prueba gráfica confirma integración, mientras la fixture de protocolo debe fallar si cambian layout o semántica.

Invariante: Una build nueva anunciada tiene una entrada de equipo registrable, no un update dirigido a un índice inexistente.

Registrar cada caso como PASS, FAIL o NO EJECUTADO, con evidencia. No convertir una omisión, un click optimista o un resultado de otro snapshot en PASS.
