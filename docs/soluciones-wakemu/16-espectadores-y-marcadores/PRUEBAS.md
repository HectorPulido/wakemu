# Pruebas y aceptación — 16

## Base existente

- [test_combat_groups.py](../../../server/tests/test_combat_groups.py): incluido en la ejecución de base registrada.

El lote común descubrió **133 tests: 123 pasaron y 10 se omitieron** (Redis real); salida 0. No implica que todas las pruebas relacionadas de esta carpeta se ejecutaran, ni que los casos nuevos pasen. Ver [VALIDACION.md](../VALIDACION.md).

Comando dirigido propuesto, desde la raíz y en entorno autorizado:

```sh
PYTHONPATH=server:server/tests PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_combat_groups -q
```

## Casos específicos que deben añadirse o reproducirse

| Caso | Acción | Resultado exigido | Estado |
| --- | --- | --- | --- |
| Marcador vivo | C entra al mapa con fightA/B | Ve solo ID real actual | Pendiente de implementar/verificar |
| Observar en turno | Snapshot y eventos concurrentes | Estado consistente y secuencia continua | Pendiente de implementar/verificar |
| Cast espectador | C pide actuar por A | Rechazo, sin costo ni evento | Pendiente de implementar/verificar |
| ACK ausente | C no responde | Participantes continúan | Pendiente de implementar/verificar |
| Fin observado | Termina combate | C vuelve al mundo y marcador desaparece | Pendiente de implementar/verificar |
| Privacidad | Fight cerrado/no visible | No snapshot ni inventario de participantes | Pendiente de implementar/verificar |

## Método y criterios

Usar personaje y almacenamiento de prueba aislados. Registrar identidad de instancia, versión, estado inicial, petición, respuesta decodificada y estado durable final. Controlar reloj y RNG en los casos deterministas. Ejecutar límites de ownership, sesión obsoleta, índices/UID inválidos y payload truncado donde apliquen.

Repetir operaciones confirmadas y cortes alrededor del commit/ACK; ninguna repetición puede duplicar consumo, recompensa o efectos. Verificar observadores y reconexión cuando el caso sea multijugador. La prueba gráfica confirma integración, mientras la fixture de protocolo debe fallar si cambian layout o semántica.

Invariante: Observar nunca concede control; un cliente lento o desconectado no bloquea el combate observado.

Registrar cada caso como PASS, FAIL o NO EJECUTADO, con evidencia. No convertir una omisión, un click optimista o un resultado de otro snapshot en PASS.
