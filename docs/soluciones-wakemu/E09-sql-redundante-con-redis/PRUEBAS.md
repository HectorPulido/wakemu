# Pruebas y aceptación — E09

## Base existente

- [test_build_journal.py](../../../server/tests/test_build_journal.py): incluido en la ejecución de base registrada.
- [test_inventory_elements.py](../../../server/tests/test_inventory_elements.py): incluido en la ejecución de base registrada.

El lote común descubrió **133 tests: 123 pasaron y 10 se omitieron** (Redis real); salida 0. No implica que todas las pruebas relacionadas de esta carpeta se ejecutaran, ni que los casos nuevos pasen. Ver [VALIDACION.md](../VALIDACION.md).

Comando dirigido propuesto, desde la raíz y en entorno autorizado:

```sh
PYTHONPATH=server:server/tests PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_build_journal test_inventory_elements -q
```

## Casos específicos que deben añadirse o reproducirse

| Caso | Acción | Resultado exigido | Estado |
| --- | --- | --- | --- |
| Hit cálido 3 veces | Cache presente y schema actual | SQL mínimo definido por política | Pendiente de implementar/verificar |
| Miss real | Sin snapshot | Una hidratación coherente y cache publicado | Pendiente de implementar/verificar |
| Writer concurrente | Mutación entre load/cache | No vuelve estado antiguo | Pendiente de implementar/verificar |
| Schema ausente | BD de prueba antigua | Migration/fallo controlados, sin DDLpor cada lectura | Pendiente de implementar/verificar |
| Permiso revocado | Cache viejo | Autorización actual sigue denegando | Pendiente de implementar/verificar |
| Caída de Redis | Journal pendiente | Sin fallback antiguo que duplicaobjetos | Pendiente de implementar/verificar |

## Método y criterios

Usar personaje y almacenamiento de prueba aislados. Registrar identidad de instancia, versión, estado inicial, petición, respuesta decodificada y estado durable final. Controlar reloj y RNG en los casos deterministas. Ejecutar límites de ownership, sesión obsoleta, índices/UID inválidos y payload truncado donde apliquen.

Repetir operaciones confirmadas y cortes alrededor del commit/ACK; ninguna repetición puede duplicar consumo, recompensa o efectos. Verificar observadores y reconexión cuando el caso sea multijugador. La prueba gráfica confirma integración, mientras la fixture de protocolo debe fallar si cambian layout o semántica.

Invariante: Una cache válida reduce SQL sin perder ownership, revocación o mutaciones pendientes.

Registrar cada caso como PASS, FAIL o NO EJECUTADO, con evidencia. No convertir una omisión, un click optimista o un resultado de otro snapshot en PASS.
