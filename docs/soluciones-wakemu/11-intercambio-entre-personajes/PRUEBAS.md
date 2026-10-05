# Pruebas y aceptación — 11

## Base existente

- [test_inventory_move.py](../../../server/tests/test_inventory_move.py): incluido en la ejecución de base registrada.
- [test_inventory_uids.py](../../../server/tests/test_inventory_uids.py): referencia existente; no ejecutado en el lote de base registrado.

El lote común descubrió **133 tests: 123 pasaron y 10 se omitieron** (Redis real); salida 0. No implica que todas las pruebas relacionadas de esta carpeta se ejecutaran, ni que los casos nuevos pasen. Ver [VALIDACION.md](../VALIDACION.md).

Comando dirigido propuesto, desde la raíz y en entorno autorizado:

```sh
PYTHONPATH=server:server/tests PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_inventory_move test_inventory_uids -q
```

## Casos específicos que deben añadirse o reproducirse

| Caso | Acción | Resultado exigido | Estado |
| --- | --- | --- | --- |
| Intercambio completo | Dos cuentas ofrecen ítem y kamas | Balances y propiedad intercambiados exactamente | Pendiente de implementar/verificar |
| Cambio tras confirmar | A edita oferta confirmada | Ambas confirmaciones invalidas; no commit | Pendiente de implementar/verificar |
| Espacio insuficiente | B recibe más slots de los disponibles | Sin consumo/transferencia parcial | Pendiente de implementar/verificar |
| Sesión sustituida | Reemplazar lease de A | Rechazo/cancelación y reservas liberadas | Pendiente de implementar/verificar |
| Crash entre fases | Corte antes/después de commit | Ambos lados old o new, nunca uno de cada | Pendiente de implementar/verificar |
| Ítem en build | Ofrecer UID referenciado | Regla explícita y ninguna build colgante | Pendiente de implementar/verificar |

## Método y criterios

Usar personaje y almacenamiento de prueba aislados. Registrar identidad de instancia, versión, estado inicial, petición, respuesta decodificada y estado durable final. Controlar reloj y RNG en los casos deterministas. Ejecutar límites de ownership, sesión obsoleta, índices/UID inválidos y payload truncado donde apliquen.

Repetir operaciones confirmadas y cortes alrededor del commit/ACK; ninguna repetición puede duplicar consumo, recompensa o efectos. Verificar observadores y reconexión cuando el caso sea multijugador. La prueba gráfica confirma integración, mientras la fixture de protocolo debe fallar si cambian layout o semántica.

Invariante: Suma de kamas y cantidades se conserva; una misma revisión requiere las dos confirmaciones actuales.

Registrar cada caso como PASS, FAIL o NO EJECUTADO, con evidencia. No convertir una omisión, un click optimista o un resultado de otro snapshot en PASS.
