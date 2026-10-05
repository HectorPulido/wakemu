# Pruebas y aceptación — 15

## Base existente

- [test_social.py](../../../server/tests/test_social.py): incluido en la ejecución de base registrada.

El lote común descubrió **133 tests: 123 pasaron y 10 se omitieron** (Redis real); salida 0. No implica que todas las pruebas relacionadas de esta carpeta se ejecutaran, ni que los casos nuevos pasen. Ver [VALIDACION.md](../VALIDACION.md).

Comando dirigido propuesto, desde la raíz y en entorno autorizado:

```sh
PYTHONPATH=server:server/tests PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_social -q
```

## Casos específicos que deben añadirse o reproducirse

| Caso | Acción | Resultado exigido | Estado |
| --- | --- | --- | --- |
| Invitar/aceptar | A/B nuevos | Un party_id y mismo roster | Pendiente de implementar/verificar |
| Doble aceptación | B acepta a A/C en carrera | Una pertenencia válida | Pendiente de implementar/verificar |
| Salida líder | A sale de A/B/C | Nuevo líder determinista y publicado | Pendiente de implementar/verificar |
| Expulsión ajena | No líder intenta expulsar | Rechazo sin cambio | Pendiente de implementar/verificar |
| Reconnect | B vuelve con nueva lease | No miembro duplicado | Pendiente de implementar/verificar |
| Party vacía | Sale último | Entidad/invitaciones cerradas según política | Pendiente de implementar/verificar |

## Método y criterios

Usar personaje y almacenamiento de prueba aislados. Registrar identidad de instancia, versión, estado inicial, petición, respuesta decodificada y estado durable final. Controlar reloj y RNG en los casos deterministas. Ejecutar límites de ownership, sesión obsoleta, índices/UID inválidos y payload truncado donde apliquen.

Repetir operaciones confirmadas y cortes alrededor del commit/ACK; ninguna repetición puede duplicar consumo, recompensa o efectos. Verificar observadores y reconexión cuando el caso sea multijugador. La prueba gráfica confirma integración, mientras la fixture de protocolo debe fallar si cambian layout o semántica.

Invariante: Cada personaje pertenece a una sola party; todos sus miembros reciben la misma revisión de roster.

Registrar cada caso como PASS, FAIL o NO EJECUTADO, con evidencia. No convertir una omisión, un click optimista o un resultado de otro snapshot en PASS.
