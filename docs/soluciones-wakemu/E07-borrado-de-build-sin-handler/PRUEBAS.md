# Pruebas y aceptación — E07

## Base existente

- [test_builds.py](../../../server/tests/test_builds.py): incluido en la ejecución de base registrada.
- [test_build_journal.py](../../../server/tests/test_build_journal.py): incluido en la ejecución de base registrada.

El lote común descubrió **133 tests: 123 pasaron y 10 se omitieron** (Redis real); salida 0. No implica que todas las pruebas relacionadas de esta carpeta se ejecutaran, ni que los casos nuevos pasen. Ver [VALIDACION.md](../VALIDACION.md).

Comando dirigido propuesto, desde la raíz y en entorno autorizado:

```sh
PYTHONPATH=server:server/tests PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_builds test_build_journal -q
```

## Casos específicos que deben añadirse o reproducirse

| Caso | Acción | Resultado exigido | Estado |
| --- | --- | --- | --- |
| Inactiva | Borrar 1 con 0 activo | Hoja retirada y objetos intactos | Pendiente de implementar/verificar |
| Activa | Borrar 1 activa | Fallback elegido y stats/deck coherentes | Pendiente de implementar/verificar |
| Build 0 | Intento protegido | Rechazo seguro | Pendiente de implementar/verificar |
| Delete duplicado | Misma solicitud repetida | Sin efecto adicional ni lock | Pendiente de implementar/verificar |
| Flush pendiente | Borrar antes decheckpoint | No resurrección enSQL | Pendiente de implementar/verificar |
| UI | Confirmar/rechazar diálogo | Controles restaurados y lista canónica | Pendiente de implementar/verificar |

## Método y criterios

Usar personaje y almacenamiento de prueba aislados. Registrar identidad de instancia, versión, estado inicial, petición, respuesta decodificada y estado durable final. Controlar reloj y RNG en los casos deterministas. Ejecutar límites de ownership, sesión obsoleta, índices/UID inválidos y payload truncado donde apliquen.

Repetir operaciones confirmadas y cortes alrededor del commit/ACK; ninguna repetición puede duplicar consumo, recompensa o efectos. Verificar observadores y reconexión cuando el caso sea multijugador. La prueba gráfica confirma integración, mientras la fixture de protocolo debe fallar si cambian layout o semántica.

Invariante: Eliminar una hoja no elimina sus objetos; selección válida y controles se restauran en todas las salidas.

Registrar cada caso como PASS, FAIL o NO EJECUTADO, con evidencia. No convertir una omisión, un click optimista o un resultado de otro snapshot en PASS.
