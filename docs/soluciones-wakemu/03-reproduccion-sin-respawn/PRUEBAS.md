# Pruebas y aceptación — 3

## Base existente

- [test_combat_groups.py](../../../server/tests/test_combat_groups.py): incluido en la ejecución de base registrada.
- [test_combat_group_store.py](../../../server/tests/test_combat_group_store.py): incluido en la ejecución de base registrada.
- [test_planting_runtime.py](../../../server/tests/test_planting_runtime.py): incluido en la ejecución de base registrada.

El lote común descubrió **133 tests: 123 pasaron y 10 se omitieron** (Redis real); salida 0. No implica que todas las pruebas relacionadas de esta carpeta se ejecutaran, ni que los casos nuevos pasen. Ver [VALIDACION.md](../VALIDACION.md).

Comando dirigido propuesto, desde la raíz y en entorno autorizado:

```sh
PYTHONPATH=server:server/tests PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_combat_groups test_combat_group_store test_planting_runtime -q
```

## Casos específicos que deben añadirse o reproducirse

| Caso | Acción | Resultado exigido | Estado |
| --- | --- | --- | --- |
| Padres compatibles | Dos adultos, zona activa, RNG favorable | Un hijo y cooldown de ambos | Pendiente de implementar/verificar |
| Grupo lleno | Reproducción en límite de miembros | Nuevo grupo solo si política/celda/cupo lo permiten | Pendiente de implementar/verificar |
| Zona saturada | Cupo máximo alcanzado | No crecimiento ilimitado | Pendiente de implementar/verificar |
| Padres en combate | Tick mientras grupo reservado | Sin reproducción hasta revalidar | Pendiente de implementar/verificar |
| Cron duplicado | Repetir birth_event_id | Mismo hijo total | Pendiente de implementar/verificar |
| Grupo derrotado | Esperar sin plantar ni reproducir | No respawn automático | Pendiente de implementar/verificar |

## Método y criterios

Usar personaje y almacenamiento de prueba aislados. Registrar identidad de instancia, versión, estado inicial, petición, respuesta decodificada y estado durable final. Controlar reloj y RNG en los casos deterministas. Ejecutar límites de ownership, sesión obsoleta, índices/UID inválidos y payload truncado donde apliquen.

Repetir operaciones confirmadas y cortes alrededor del commit/ACK; ninguna repetición puede duplicar consumo, recompensa o efectos. Verificar observadores y reconexión cuando el caso sea multijugador. La prueba gráfica confirma integración, mientras la fixture de protocolo debe fallar si cambian layout o semántica.

Invariante: Cada nueva unidad tiene origen durable de siembra o reproducción; matar y esperar no genera unidades.

Registrar cada caso como PASS, FAIL o NO EJECUTADO, con evidencia. No convertir una omisión, un click optimista o un resultado de otro snapshot en PASS.
