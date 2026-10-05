# Pruebas y aceptación — 19

## Base existente

- [test_monster_wander.py](../../../server/tests/test_monster_wander.py): incluido en la ejecución de base registrada.
- [test_combat_groups.py](../../../server/tests/test_combat_groups.py): incluido en la ejecución de base registrada.

El lote común descubrió **133 tests: 123 pasaron y 10 se omitieron** (Redis real); salida 0. No implica que todas las pruebas relacionadas de esta carpeta se ejecutaran, ni que los casos nuevos pasen. Ver [VALIDACION.md](../VALIDACION.md).

Comando dirigido propuesto, desde la raíz y en entorno autorizado:

```sh
PYTHONPATH=server:server/tests PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_monster_wander test_combat_groups -q
```

## Casos específicos que deben añadirse o reproducirse

| Caso | Acción | Resultado exigido | Estado |
| --- | --- | --- | --- |
| p frontera | Draw 0,2499/0,25 | Mover/no mover según contrato | Pendiente de implementar/verificar |
| Longitud aleatoria | RNG en min/max pasos | Todos los pasos legales y acotados | Pendiente de implementar/verificar |
| Mapa vacío | Ningún jugador en instancia | Cero planes/movimientos | Pendiente de implementar/verificar |
| Grupo en combate | Vence evaluación | Sin movementpacket | Pendiente de implementar/verificar |
| Carrera con reserva | Plan externo mientras empieza combate | CAS descarta plan | Pendiente de implementar/verificar |
| Carga 32 | Medir tick y esperas | Sin escaneo completo por grupo ni lock largo | Pendiente de implementar/verificar |

## Método y criterios

Usar personaje y almacenamiento de prueba aislados. Registrar identidad de instancia, versión, estado inicial, petición, respuesta decodificada y estado durable final. Controlar reloj y RNG en los casos deterministas. Ejecutar límites de ownership, sesión obsoleta, índices/UID inválidos y payload truncado donde apliquen.

Repetir operaciones confirmadas y cortes alrededor del commit/ACK; ninguna repetición puede duplicar consumo, recompensa o efectos. Verificar observadores y reconexión cuando el caso sea multijugador. La prueba gráfica confirma integración, mientras la fixture de protocolo debe fallar si cambian layout o semántica.

Invariante: Solo zonas presentes simulan; ninguna ruta mueve miembros durante combate/recolección o por celdas ilegales.

Registrar cada caso como PASS, FAIL o NO EJECUTADO, con evidencia. No convertir una omisión, un click optimista o un resultado de otro snapshot en PASS.
