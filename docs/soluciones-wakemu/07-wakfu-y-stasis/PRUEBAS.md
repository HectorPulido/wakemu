# Pruebas y aceptación — 7

## Base existente

- [test_planting_context.py](../../../server/tests/test_planting_context.py): incluido en la ejecución de base registrada.
- [test_planting.py](../../../server/tests/test_planting.py): incluido en la ejecución de base registrada.
- [test_monster_collect.py](../../../server/tests/test_monster_collect.py): incluido en la ejecución de base registrada.

El lote común descubrió **133 tests: 123 pasaron y 10 se omitieron** (Redis real); salida 0. No implica que todas las pruebas relacionadas de esta carpeta se ejecutaran, ni que los casos nuevos pasen. Ver [VALIDACION.md](../VALIDACION.md).

Comando dirigido propuesto, desde la raíz y en entorno autorizado:

```sh
PYTHONPATH=server:server/tests PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_planting_context test_planting test_monster_collect -q
```

## Casos específicos que deben añadirse o reproducirse

| Caso | Acción | Resultado exigido | Estado |
| --- | --- | --- | --- |
| Acción favorable | Estado poblacional en rango definido | Delta de Wakfu según fórmula | Pendiente de implementar/verificar |
| Acción desfavorable | Estado fuera del rango definido | Delta Stasis según fórmula | Pendiente de implementar/verificar |
| Cancelación | No se confirma cosecha | Sin delta personal | Pendiente de implementar/verificar |
| Límite | Valor cerca de máximo/mínimo | Clamp exacto, sin wrap | Pendiente de implementar/verificar |
| Reintento | Resultado de acción repetido | Una variación total | Pendiente de implementar/verificar |
| Dos acciones | Confirmar concurrentemente | Ambos recibos y suma consistente | Pendiente de implementar/verificar |

## Método y criterios

Usar personaje y almacenamiento de prueba aislados. Registrar identidad de instancia, versión, estado inicial, petición, respuesta decodificada y estado durable final. Controlar reloj y RNG en los casos deterministas. Ejecutar límites de ownership, sesión obsoleta, índices/UID inválidos y payload truncado donde apliquen.

Repetir operaciones confirmadas y cortes alrededor del commit/ACK; ninguna repetición puede duplicar consumo, recompensa o efectos. Verificar observadores y reconexión cuando el caso sea multijugador. La prueba gráfica confirma integración, mientras la fixture de protocolo debe fallar si cambian layout o semántica.

Invariante: Solo acciones confirmadas alteran progreso una vez; los valores pertenecen al personaje correcto.

Registrar cada caso como PASS, FAIL o NO EJECUTADO, con evidencia. No convertir una omisión, un click optimista o un resultado de otro snapshot en PASS.
