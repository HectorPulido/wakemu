# Pruebas y aceptación — 31

## Base existente

- [test_combat_placement_cells.py](../../../server/tests/test_combat_placement_cells.py): incluido en la ejecución de base registrada.

El lote común descubrió **133 tests: 123 pasaron y 10 se omitieron** (Redis real); salida 0. No implica que todas las pruebas relacionadas de esta carpeta se ejecutaran, ni que los casos nuevos pasen. Ver [VALIDACION.md](../VALIDACION.md).

Comando dirigido propuesto, desde la raíz y en entorno autorizado:

```sh
PYTHONPATH=server:server/tests PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_combat_placement_cells -q
```

## Casos específicos que deben añadirse o reproducirse

| Caso | Acción | Resultado exigido | Estado |
| --- | --- | --- | --- |
| Igual seed | Mismas posiciones/terrain | Mismo layout reproducible | Pendiente de implementar/verificar |
| Seeds variadas | 20 encuentros iguales | Diversidad según política acordada | Pendiente de implementar/verificar |
| Mapa pequeño | Pocos candidatos/desnivel | Formación legal o fallo seguro | Pendiente de implementar/verificar |
| Dos equipos | Comprobar conjuntos | Sin intersección ni celdas inaccesibles | Pendiente de implementar/verificar |
| Reconnect/join | Reenviar bootstrap | Layout elegido conservado | Pendiente de implementar/verificar |
| Carga | Arena grande y varios actores | Costo acotado/indexado | Pendiente de implementar/verificar |

## Método y criterios

Usar personaje y almacenamiento de prueba aislados. Registrar identidad de instancia, versión, estado inicial, petición, respuesta decodificada y estado durable final. Controlar reloj y RNG en los casos deterministas. Ejecutar límites de ownership, sesión obsoleta, índices/UID inválidos y payload truncado donde apliquen.

Repetir operaciones confirmadas y cortes alrededor del commit/ACK; ninguna repetición puede duplicar consumo, recompensa o efectos. Verificar observadores y reconexión cuando el caso sea multijugador. La prueba gráfica confirma integración, mientras la fixture de protocolo debe fallar si cambian layout o semántica.

Invariante: Layout elegido una vez por encuentro, legal para todos y persistente a través de sesiones.

Registrar cada caso como PASS, FAIL o NO EJECUTADO, con evidencia. No convertir una omisión, un click optimista o un resultado de otro snapshot en PASS.
