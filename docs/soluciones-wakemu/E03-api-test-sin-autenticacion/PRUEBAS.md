# Pruebas y aceptación — E03

## Base existente

- [test_chat_console.py](../../../server/tests/test_chat_console.py): incluido en la ejecución de base registrada.

El lote común descubrió **133 tests: 123 pasaron y 10 se omitieron** (Redis real); salida 0. No implica que todas las pruebas relacionadas de esta carpeta se ejecutaran, ni que los casos nuevos pasen. Ver [VALIDACION.md](../VALIDACION.md).

Comando dirigido propuesto, desde la raíz y en entorno autorizado:

```sh
PYTHONPATH=server:server/tests PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_chat_console -q
```

## Casos específicos que deben añadirse o reproducirse

| Caso | Acción | Resultado exigido | Estado |
| --- | --- | --- | --- |
| Anónimocommand | POSTsinBearer | Denegado antes dejob | Pendiente de implementar/verificar |
| Normalcommand | Bearerválido noadmin | 403 sinmutation | Pendiente de implementar/verificar |
| Targetajeno | Adminsegúnpolítica/normal | Ownership separado ycorrecto | Pendiente de implementar/verificar |
| Cronlimitado | Tokenservicio taskycommand | Solo taskpermitida | Pendiente de implementar/verificar |
| GETajeno | Handledeotracuenta | Sin datos dejob | Pendiente de implementar/verificar |
| Revocadocolajob | Token revocado antes de ejecución | Política revalidada, sinbypass | Pendiente de implementar/verificar |

## Método y criterios

Usar personaje y almacenamiento de prueba aislados. Registrar identidad de instancia, versión, estado inicial, petición, respuesta decodificada y estado durable final. Controlar reloj y RNG en los casos deterministas. Ejecutar límites de ownership, sesión obsoleta, índices/UID inválidos y payload truncado donde apliquen.

Repetir operaciones confirmadas y cortes alrededor del commit/ACK; ninguna repetición puede duplicar consumo, recompensa o efectos. Verificar observadores y reconexión cuando el caso sea multijugador. La prueba gráfica confirma integración, mientras la fixture de protocolo debe fallar si cambian layout o semántica.

Invariante: Ningún endpoint de prueba elude autenticación por estar antes de la rama común.

Registrar cada caso como PASS, FAIL o NO EJECUTADO, con evidencia. No convertir una omisión, un click optimista o un resultado de otro snapshot en PASS.
