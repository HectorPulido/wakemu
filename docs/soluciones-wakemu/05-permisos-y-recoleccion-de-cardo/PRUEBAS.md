# Pruebas y aceptación — 5

## Base existente

- [test_planting.py](../../../server/tests/test_planting.py): incluido en la ejecución de base registrada.
- [test_monster_collect.py](../../../server/tests/test_monster_collect.py): incluido en la ejecución de base registrada.

El lote común descubrió **133 tests: 123 pasaron y 10 se omitieron** (Redis real); salida 0. No implica que todas las pruebas relacionadas de esta carpeta se ejecutaran, ni que los casos nuevos pasen. Ver [VALIDACION.md](../VALIDACION.md).

Comando dirigido propuesto, desde la raíz y en entorno autorizado:

```sh
PYTHONPATH=server:server/tests PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_planting test_monster_collect -q
```

## Casos específicos que deben añadirse o reproducirse

| Caso | Acción | Resultado exigido | Estado |
| --- | --- | --- | --- |
| Recurso libre | Cardo maduro, acción correcta | Acción termina y producto/XP una vez | Pendiente de implementar/verificar |
| Segundo recolector | Dos cuentas sobre mismo recurso | Reserva única y rechazo coherente | Pendiente de implementar/verificar |
| Etapa temprana | Acción final sobre etapa inicial | Rechazo por etapa, no propiedad falsa | Pendiente de implementar/verificar |
| Distancia/altura | Clic fuera de alcance | Sin ocupación ni recompensa | Pendiente de implementar/verificar |
| Cancelar/desconectar | Salir durante animación | Reserva liberada; no cosecha duplicada | Pendiente de implementar/verificar |
| UID fuera de instancia | Reutilizar UID de otra instancia | Rechazo sin revelar/alterar recurso ajeno | Pendiente de implementar/verificar |

## Método y criterios

Usar personaje y almacenamiento de prueba aislados. Registrar identidad de instancia, versión, estado inicial, petición, respuesta decodificada y estado durable final. Controlar reloj y RNG en los casos deterministas. Ejecutar límites de ownership, sesión obsoleta, índices/UID inválidos y payload truncado donde apliquen.

Repetir operaciones confirmadas y cortes alrededor del commit/ACK; ninguna repetición puede duplicar consumo, recompensa o efectos. Verificar observadores y reconexión cuando el caso sea multijugador. La prueba gráfica confirma integración, mientras la fixture de protocolo debe fallar si cambian layout o semántica.

Invariante: Solo una cosecha por transición de recurso; ocupación temporal y propiedad no se confunden.

Registrar cada caso como PASS, FAIL o NO EJECUTADO, con evidencia. No convertir una omisión, un click optimista o un resultado de otro snapshot en PASS.
