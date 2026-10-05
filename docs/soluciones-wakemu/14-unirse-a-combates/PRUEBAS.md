# Pruebas y aceptación — 14

## Base existente

- [test_combat_groups.py](../../../server/tests/test_combat_groups.py): incluido en la ejecución de base registrada.
- [test_combat_placement_cells.py](../../../server/tests/test_combat_placement_cells.py): incluido en la ejecución de base registrada.

El lote común descubrió **133 tests: 123 pasaron y 10 se omitieron** (Redis real); salida 0. No implica que todas las pruebas relacionadas de esta carpeta se ejecutaran, ni que los casos nuevos pasen. Ver [VALIDACION.md](../VALIDACION.md).

Comando dirigido propuesto, desde la raíz y en entorno autorizado:

```sh
PYTHONPATH=server:server/tests PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_combat_groups test_combat_placement_cells -q
```

## Casos específicos que deben añadirse o reproducirse

| Caso | Acción | Resultado exigido | Estado |
| --- | --- | --- | --- |
| Join en colocación | B entra al combate de A | Mismo fight_id, actorB y celdas en ambos | Pendiente de implementar/verificar |
| Join tardío | Fase active | Rechazo claro sin reserva | Pendiente de implementar/verificar |
| Cupo lleno | Equipo sin hueco | No actor parcial | Pendiente de implementar/verificar |
| Carrera ready/join | Dos solicitudes concurrentes | Versión resuelve una transición consistente | Pendiente de implementar/verificar |
| Snapshot concurrente | Eventos durante bootstrapB | Sin huecos/duplicación de secuencia | Pendiente de implementar/verificar |
| DesconexiónB | A sigue en encuentro | Salida parcial segura según política | Pendiente de implementar/verificar |

## Método y criterios

Usar personaje y almacenamiento de prueba aislados. Registrar identidad de instancia, versión, estado inicial, petición, respuesta decodificada y estado durable final. Controlar reloj y RNG en los casos deterministas. Ejecutar límites de ownership, sesión obsoleta, índices/UID inválidos y payload truncado donde apliquen.

Repetir operaciones confirmadas y cortes alrededor del commit/ACK; ninguna repetición puede duplicar consumo, recompensa o efectos. Verificar observadores y reconexión cuando el caso sea multijugador. La prueba gráfica confirma integración, mientras la fixture de protocolo debe fallar si cambian layout o semántica.

Invariante: Todas las sesiones ven un único encuentro; entrar tarde no altera sus actores ni su turno.

Registrar cada caso como PASS, FAIL o NO EJECUTADO, con evidencia. No convertir una omisión, un click optimista o un resultado de otro snapshot en PASS.
