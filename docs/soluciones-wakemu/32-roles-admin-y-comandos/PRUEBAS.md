# Pruebas y aceptación — 32

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
| Normal chat/API | Intentar !item/!nivel | Rechazo y estado intacto | Pendiente de implementar/verificar |
| Admin consoleon | Comando legal targetpermitido | Mutación una vez y auditoría | Pendiente de implementar/verificar |
| Anónimo | POST/testcommand | 401/403 según contrato, sin handle ejecutable | Pendiente de implementar/verificar |
| Revocación | Revoke tras login | Comando posterior rechazado | Pendiente de implementar/verificar |
| Consolaoff | Admin autorizado | No bypass de interruptor global | Pendiente de implementar/verificar |
| Cron | Principal limitado intenta comando | Flush permitido, !item denegado | Pendiente de implementar/verificar |

## Método y criterios

Usar personaje y almacenamiento de prueba aislados. Registrar identidad de instancia, versión, estado inicial, petición, respuesta decodificada y estado durable final. Controlar reloj y RNG en los casos deterministas. Ejecutar límites de ownership, sesión obsoleta, índices/UID inválidos y payload truncado donde apliquen.

Repetir operaciones confirmadas y cortes alrededor del commit/ACK; ninguna repetición puede duplicar consumo, recompensa o efectos. Verificar observadores y reconexión cuando el caso sea multijugador. La prueba gráfica confirma integración, mientras la fixture de protocolo debe fallar si cambian layout o semántica.

Invariante: Autenticación, rol, ownership y lease se comprueban separadamente antes de cualquier mutación.

Registrar cada caso como PASS, FAIL o NO EJECUTADO, con evidencia. No convertir una omisión, un click optimista o un resultado de otro snapshot en PASS.
