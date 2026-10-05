# Pruebas y aceptación — 28

## Base existente

- [test_planting_context.py](../../../server/tests/test_planting_context.py): incluido en la ejecución de base registrada.
- [test_ring_build_integration.py](../../../server/tests/test_ring_build_integration.py): referencia existente; no ejecutado en el lote de base registrado.

El lote común descubrió **133 tests: 123 pasaron y 10 se omitieron** (Redis real); salida 0. No implica que todas las pruebas relacionadas de esta carpeta se ejecutaran, ni que los casos nuevos pasen. Ver [VALIDACION.md](../VALIDACION.md).

Comando dirigido propuesto, desde la raíz y en entorno autorizado:

```sh
PYTHONPATH=server:server/tests PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_planting_context test_ring_build_integration -q
```

## Casos específicos que deben añadirse o reproducirse

| Caso | Acción | Resultado exigido | Estado |
| --- | --- | --- | --- |
| Entrar/salir | Zona con bonus conocido | Gana y pierde exactamente valor | Pendiente de implementar/verificar |
| Reconnect 10 veces | Mismo lugar | No acumulación | Pendiente de implementar/verificar |
| Condición cambia | Población pierde satisfacción | Todos pierden bonus según regla | Pendiente de implementar/verificar |
| Build switch | Cambiar aptitudes en zona | Bonus zonal una vez | Pendiente de implementar/verificar |
| Combate | Entrar o cambiar condición durante fight | Snapshot/dinámica según política | Pendiente de implementar/verificar |
| Zona neutral | Bonus requiere nación | No se aplica alineamiento inexistente | Pendiente de implementar/verificar |

## Método y criterios

Usar personaje y almacenamiento de prueba aislados. Registrar identidad de instancia, versión, estado inicial, petición, respuesta decodificada y estado durable final. Controlar reloj y RNG en los casos deterministas. Ejecutar límites de ownership, sesión obsoleta, índices/UID inválidos y payload truncado donde apliquen.

Repetir operaciones confirmadas y cortes alrededor del commit/ACK; ninguna repetición puede duplicar consumo, recompensa o efectos. Verificar observadores y reconexión cuando el caso sea multijugador. La prueba gráfica confirma integración, mientras la fixture de protocolo debe fallar si cambian layout o semántica.

Invariante: Cada fuente contribuye una vez; salir o perder condición restaura baseline sin drifts.

Registrar cada caso como PASS, FAIL o NO EJECUTADO, con evidencia. No convertir una omisión, un click optimista o un resultado de otro snapshot en PASS.
