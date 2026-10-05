# Pruebas y aceptación — 2

## Base existente

- [test_planting_runtime.py](../../../server/tests/test_planting_runtime.py): incluido en la ejecución de base registrada.
- [test_monsters.py](../../../server/tests/test_monsters.py): referencia existente; no ejecutado en el lote de base registrado.
- [test_combat_group_store.py](../../../server/tests/test_combat_group_store.py): incluido en la ejecución de base registrada.

El lote común descubrió **133 tests: 123 pasaron y 10 se omitieron** (Redis real); salida 0. No implica que todas las pruebas relacionadas de esta carpeta se ejecutaran, ni que los casos nuevos pasen. Ver [VALIDACION.md](../VALIDACION.md).

Comando dirigido propuesto, desde la raíz y en entorno autorizado:

```sh
PYTHONPATH=server:server/tests PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_planting_runtime test_monsters test_combat_group_store -q
```

## Casos específicos que deben añadirse o reproducirse

| Caso | Acción | Resultado exigido | Estado |
| --- | --- | --- | --- |
| Bebé confirmado | Reloj antes/después del plazo activo | Un miembro cambia a la referencia adulta correcta | Pendiente de implementar/verificar |
| Familia sin transición | Procesar especie no catalogada | Sin transformación inventada | Pendiente de implementar/verificar |
| Zona vacía | Ausencia supera el plazo | Tiempo pausado conforme al 20 | Pendiente de implementar/verificar |
| En combate | Vence durante turno | Forma del combate no cambia; transición se revalida después | Pendiente de implementar/verificar |
| Tick repetido | Procesar dos veces la misma revisión | Una transición, sin nuevo miembro | Pendiente de implementar/verificar |
| Recuperación | Reabrir storage con etapa pendiente | Misma etapa y tiempo, no reinicio arbitrario | Pendiente de implementar/verificar |

## Método y criterios

Usar personaje y almacenamiento de prueba aislados. Registrar identidad de instancia, versión, estado inicial, petición, respuesta decodificada y estado durable final. Controlar reloj y RNG en los casos deterministas. Ejecutar límites de ownership, sesión obsoleta, índices/UID inválidos y payload truncado donde apliquen.

Repetir operaciones confirmadas y cortes alrededor del commit/ACK; ninguna repetición puede duplicar consumo, recompensa o efectos. Verificar observadores y reconexión cuando el caso sea multijugador. La prueba gráfica confirma integración, mientras la fixture de protocolo debe fallar si cambian layout o semántica.

Invariante: Madurar no añade población; un miembro solo atraviesa transiciones legales de su familia.

Registrar cada caso como PASS, FAIL o NO EJECUTADO, con evidencia. No convertir una omisión, un click optimista o un resultado de otro snapshot en PASS.
