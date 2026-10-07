# Pruebas y aceptación — 9

## Base existente

- [test_combat_rewards.py](../../../server/tests/test_combat_rewards.py): incluido en la ejecución de base registrada.
- [test_builds.py](../../../server/tests/test_builds.py): incluido en la ejecución de base registrada.
- [test_aptitudes.py](../../../server/tests/test_aptitudes.py): incluido en la ejecución de base registrada.

El lote común descubrió **133 tests: 123 pasaron y 10 se omitieron** (Redis real); salida 0. No implica que todas las pruebas relacionadas de esta carpeta se ejecutaran, ni que los casos nuevos pasen. Ver [VALIDACION.md](../VALIDACION.md).

Comando dirigido propuesto, desde la raíz y en entorno autorizado:

```sh
PYTHONPATH=server:server/tests PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_combat_rewards test_builds test_aptitudes -q
```

## Casos específicos que deben añadirse o reproducirse

| Caso | Acción | Resultado exigido | Estado |
| --- | --- | --- | --- |
| Default 0 | Victoria con política desactivada | Sin XP; se informa política, no falla desconocida | Pendiente de implementar/verificar |
| Multiplicador 2 | Base conocida y victoria | XP exacta y redondeo acordado | Pendiente de implementar/verificar |
| Cruce 50 | XP suficiente para nivel 50 | Nivel y desbloqueos se refrescan; acotar comportamiento de 34 | Pendiente de implementar/verificar |
| Hoja nivel fijo | Subida 49→50 con aptitudes 49 | Sin excepción ni commit parcial | Pendiente de implementar/verificar |
| Retry premio | Cerrar/restaurar el mismo combate | Una recompensa y delta | Pendiente de implementar/verificar |
| Abandono/derrota | Final no elegible | Sin XP indebida | Pendiente de implementar/verificar |

## Método y criterios

Usar personaje y almacenamiento de prueba aislados. Registrar identidad de instancia, versión, estado inicial, petición, respuesta decodificada y estado durable final. Controlar reloj y RNG en los casos deterministas. Ejecutar límites de ownership, sesión obsoleta, índices/UID inválidos y payload truncado donde apliquen.

Repetir operaciones confirmadas y cortes alrededor del commit/ACK; ninguna repetición puede duplicar consumo, recompensa o efectos. Verificar observadores y reconexión cuando el caso sea multijugador. La prueba gráfica confirma integración, mientras la fixture de protocolo debe fallar si cambian layout o semántica.

Invariante: El recibo fija recompensa y versión; el nivel visible, XP y hojas nunca quedan parcialmente actualizados.

Registrar cada caso como PASS, FAIL o NO EJECUTADO, con evidencia. No convertir una omisión, un click optimista o un resultado de otro snapshot en PASS.

## Aceptación visual Adael — 7 de octubre

Usuario confirma dos victorias: primera121XP, nivel1→2, +38kamas y12325×3; segunda122XP, +30kamas y pila12325×6. PostgreSQL acredita fight12(start_xp0,end_xp121) y fight13(121→243). Ventana Personaje muestra141/360 dentro del nivel2:243 menos102 acumulados del nivel anterior. Wallet compartido de account2:161; suma de premios68. Persistencia tras selector/cliente/world pendiente de confirmación manual.
