# Pruebas y aceptación — 34

## Base existente

- [test_builds.py](../../../server/tests/test_builds.py): incluido en la ejecución de base registrada.
- [test_build_journal.py](../../../server/tests/test_build_journal.py): incluido en la ejecución de base registrada.
- [test_aptitudes.py](../../../server/tests/test_aptitudes.py): incluido en la ejecución de base registrada.
- [test_ring_build_integration.py](../../../server/tests/test_ring_build_integration.py): referencia existente; no ejecutado en el lote de base registrado.

El lote común descubrió **133 tests: 123 pasaron y 10 se omitieron** (Redis real); salida 0. No implica que todas las pruebas relacionadas de esta carpeta se ejecutaran, ni que los casos nuevos pasen. Ver [VALIDACION.md](../VALIDACION.md).

Comando dirigido propuesto, desde la raíz y en entorno autorizado:

```sh
PYTHONPATH=server:server/tests PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_builds test_build_journal test_aptitudes test_ring_build_integration -q
```

## Casos específicos que deben añadirse o reproducirse

| Caso | Acción | Resultado exigido | Estado |
| --- | --- | --- | --- |
| Umbral | Cruzar 49/50/51 por XP y comando | Colecciones y desbloqueo coherentes | Pendiente de implementar/verificar |
| Secundaria vacía | Abrir antes del primer guardado | Cuatro hojas registradas; ningún modelo nulo | Pendiente de implementar/verificar |
| Activación | Pulsar Activar sobre índice 1 | Solicitud manejada y selección persistida | Pendiente de implementar/verificar |
| Estadísticas | Alternar hojas con equipo y aptitudes distintos | Valores desde la activa, sin acumulación | Pendiente de implementar/verificar |
| Deck exclusivo | Lanzar hechizo presente solo en deck 1 | Permitido en 1 y rechazado en 0 sin consumo | Pendiente de implementar/verificar |
| Recuperación | Reconectar antes y después del flush | Misma selección y mismas hojas | Pendiente de implementar/verificar |
| Nivel fijo | Subir 49→50 con hoja limitada | Sin commit parcial | Pendiente de implementar/verificar |
| Borrado y cupo | Borrar activa y crear en el límite | Fallback válido y UID conservados | Pendiente de implementar/verificar |

## Método y criterios

Usar personaje y almacenamiento de prueba aislados. Registrar identidad de instancia, versión, estado inicial, petición, respuesta decodificada y estado durable final. Controlar reloj y RNG en los casos deterministas. Ejecutar límites de ownership, sesión obsoleta, índices/UID inválidos y payload truncado donde apliquen.

Repetir operaciones confirmadas y cortes alrededor del commit/ACK; ninguna repetición puede duplicar consumo, recompensa o efectos. Verificar observadores y reconexión cuando el caso sea multijugador. La prueba gráfica confirma integración, mientras la fixture de protocolo debe fallar si cambian layout o semántica.

Invariante: Metadata, equipo, aptitudes, deck y selección comparten índice y revisión; el check visual Activa no prueba autoridad del servidor.

Registrar cada caso como PASS, FAIL o NO EJECUTADO, con evidencia. No convertir una omisión, un click optimista o un resultado de otro snapshot en PASS.
