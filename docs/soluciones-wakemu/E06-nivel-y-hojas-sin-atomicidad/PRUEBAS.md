# Pruebas y aceptación — E06

## Base existente

- [test_aptitudes.py](../../../server/tests/test_aptitudes.py): incluido en la ejecución de base registrada.
- [test_build_journal.py](../../../server/tests/test_build_journal.py): incluido en la ejecución de base registrada.
- [test_combat_rewards.py](../../../server/tests/test_combat_rewards.py): incluido en la ejecución de base registrada.

El lote común descubrió **133 tests: 123 pasaron y 10 se omitieron** (Redis real); salida 0. No implica que todas las pruebas relacionadas de esta carpeta se ejecutaran, ni que los casos nuevos pasen. Ver [VALIDACION.md](../VALIDACION.md).

Comando dirigido propuesto, desde la raíz y en entorno autorizado:

```sh
PYTHONPATH=server:server/tests PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_aptitudes test_build_journal test_combat_rewards -q
```

## Casos específicos que deben añadirse o reproducirse

| Caso | Acción | Resultado exigido | Estado |
| --- | --- | --- | --- |
| Fixture 49→50 | Hoja fija 49 y command | Resultado coherente o rechazo total, nunca nivel 50/max 540 parcial | Pendiente de implementar/verificar |
| Hoja-1 | Misma subida con nivel real | Presupuesto y salud actualizados | Pendiente de implementar/verificar |
| Hoja modulada | Cap inferior legítimo | Regla validada sin elevar stats ilegalmente | Pendiente de implementar/verificar |
| RewardXP | Cruce por combate | Mismas garantías de atomicidad | Pendiente de implementar/verificar |
| Journal pending | Subida antes de flush | Hydration/recovery válidas | Pendiente de implementar/verificar |
| Fallo de evaluador | Inyección antes de commit | Estado anterior completo preservado | Pendiente de implementar/verificar |

## Método y criterios

Usar personaje y almacenamiento de prueba aislados. Registrar identidad de instancia, versión, estado inicial, petición, respuesta decodificada y estado durable final. Controlar reloj y RNG en los casos deterministas. Ejecutar límites de ownership, sesión obsoleta, índices/UID inválidos y payload truncado donde apliquen.

Repetir operaciones confirmadas y cortes alrededor del commit/ACK; ninguna repetición puede duplicar consumo, recompensa o efectos. Verificar observadores y reconexión cuando el caso sea multijugador. La prueba gráfica confirma integración, mientras la fixture de protocolo debe fallar si cambian layout o semántica.

Invariante: Nivel/XP y hojas compatibles cambian juntos; un evaluador no puede fallar después de dejar media transición confirmada.

Registrar cada caso como PASS, FAIL o NO EJECUTADO, con evidencia. No convertir una omisión, un click optimista o un resultado de otro snapshot en PASS.
