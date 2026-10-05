# Pruebas y aceptación — E08

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
| Último permitido | Crear hoja en allowed_max | Success y cuatro hojas | Pendiente de implementar/verificar |
| Primero inválido | Index fuera catálogo | Rechazo coherente con UI | Pendiente de implementar/verificar |
| Índice 3 actual | Fixture de backend | Reproduce rechazo existente; futura regla lo redefine explícitamente | Pendiente de implementar/verificar |
| Delete/recreate | Liberar cupo | Sin sobrescribir otras hojas | Pendiente de implementar/verificar |
| Signedbyte | Borde de rango nativo | Sin desbordamiento ni alias de índice | Pendiente de implementar/verificar |
| Legacy | Más hojas que nuevo cupo | Migration declarada, no pérdida oculta | Pendiente de implementar/verificar |

## Método y criterios

Usar personaje y almacenamiento de prueba aislados. Registrar identidad de instancia, versión, estado inicial, petición, respuesta decodificada y estado durable final. Controlar reloj y RNG en los casos deterministas. Ejecutar límites de ownership, sesión obsoleta, índices/UID inválidos y payload truncado donde apliquen.

Repetir operaciones confirmadas y cortes alrededor del commit/ACK; ninguna repetición puede duplicar consumo, recompensa o efectos. Verificar observadores y reconexión cuando el caso sea multijugador. La prueba gráfica confirma integración, mientras la fixture de protocolo debe fallar si cambian layout o semántica.

Invariante: El cupo que la interfaz ofrece corresponde al que el servidor valida; cada índice conserva su identidad.

Registrar cada caso como PASS, FAIL o NO EJECUTADO, con evidencia. No convertir una omisión, un click optimista o un resultado de otro snapshot en PASS.
