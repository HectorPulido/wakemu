# Pruebas y aceptación — 8

## Base existente

- [test_profession_store.py](../../../server/tests/test_profession_store.py): incluido en la ejecución de base registrada.
- [test_planting.py](../../../server/tests/test_planting.py): incluido en la ejecución de base registrada.
- [test_monster_collect.py](../../../server/tests/test_monster_collect.py): incluido en la ejecución de base registrada.

El lote común descubrió **133 tests: 123 pasaron y 10 se omitieron** (Redis real); salida 0. No implica que todas las pruebas relacionadas de esta carpeta se ejecutaran, ni que los casos nuevos pasen. Ver [VALIDACION.md](../VALIDACION.md).

Comando dirigido propuesto, desde la raíz y en entorno autorizado:

```sh
PYTHONPATH=server:server/tests PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_profession_store test_planting test_monster_collect -q
```

## Casos específicos que deben añadirse o reproducirse

| Caso | Acción | Resultado exigido | Estado |
| --- | --- | --- | --- |
| Primer punto | Oficio aprendido nivel 0 | XP cambia y permanece | Pendiente de implementar/verificar |
| Umbral | XP justo para nivel siguiente | Nivel/acciones actualizados inmediatamente | Pendiente de implementar/verificar |
| Varios niveles | Recompensa grande controlada | Nivel según curva, no +1 fijo | Pendiente de implementar/verificar |
| Fallo/cancelación | Acción no confirmada | XP conforme a regla de fallo, nunca accidental | Pendiente de implementar/verificar |
| Retry | Duplicar operación de crafting | Una recompensa XP/producto | Pendiente de implementar/verificar |
| Migración | Profesión vieja solo con nivel | Nivel preservado y XP coherente según política | Pendiente de implementar/verificar |

## Método y criterios

Usar personaje y almacenamiento de prueba aislados. Registrar identidad de instancia, versión, estado inicial, petición, respuesta decodificada y estado durable final. Controlar reloj y RNG en los casos deterministas. Ejecutar límites de ownership, sesión obsoleta, índices/UID inválidos y payload truncado donde apliquen.

Repetir operaciones confirmadas y cortes alrededor del commit/ACK; ninguna repetición puede duplicar consumo, recompensa o efectos. Verificar observadores y reconexión cuando el caso sea multijugador. La prueba gráfica confirma integración, mientras la fixture de protocolo debe fallar si cambian layout o semántica.

Invariante: XP total y nivel son coherentes; una acción confirmada no concede dos premios por reconexión.

Registrar cada caso como PASS, FAIL o NO EJECUTADO, con evidencia. No convertir una omisión, un click optimista o un resultado de otro snapshot en PASS.
