# Pruebas y aceptación — 22

## Base existente

- [test_inventory_elements.py](../../../server/tests/test_inventory_elements.py): incluido en la ejecución de base registrada.
- [test_inventory_actions.py](../../../server/tests/test_inventory_actions.py): referencia existente; no ejecutado en el lote de base registrado.
- [test_inventory_move.py](../../../server/tests/test_inventory_move.py): incluido en la ejecución de base registrada.
- [test_ring_build_integration.py](../../../server/tests/test_ring_build_integration.py): referencia existente; no ejecutado en el lote de base registrado.

El lote común descubrió **133 tests: 123 pasaron y 10 se omitieron** (Redis real); salida 0. No implica que todas las pruebas relacionadas de esta carpeta se ejecutaran, ni que los casos nuevos pasen. Ver [VALIDACION.md](../VALIDACION.md).

Comando dirigido propuesto, desde la raíz y en entorno autorizado:

```sh
PYTHONPATH=server:server/tests PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_inventory_elements test_inventory_actions test_inventory_move test_ring_build_integration -q
```

## Casos específicos que deben añadirse o reproducirse

| Caso | Acción | Resultado exigido | Estado |
| --- | --- | --- | --- |
| Identificar por primera vez | UID legacy propio con cantidad 1 | Una selección/sorteo persistidos y tooltip coherente | Pendiente de implementar/verificar |
| Doble clic/retry | Repetir confirmación o reconnect | No reroll, consumo o sockets adicionales | Pendiente de implementar/verificar |
| Stack individual | Identificar una unidad de stack 3 | Una instancia independiente y dos restantes; suma 3 | Pendiente de implementar/verificar |
| Reasignar elementos | Cambiar elección con objeto equipado | Solo elementos elegidos aplicados una vez | Pendiente de implementar/verificar |
| Reciclar/sacrificar | Intento legal y retry tras commit | Consumo 1 y producto/cargas una vez | Pendiente de implementar/verificar |
| Sublimación válida/inválida | Orden compatible e incompatible | Solo válida consume/aplica; inválida conserva scroll | Pendiente de implementar/verificar |
| Retirar efecto | Inversión conocida y retirada repetida | Refund según fórmula una sola vez | Pendiente de implementar/verificar |
| Recovery/transfer | Flush, mover dueño y recargar | Propiedades/UID/inversión conservados, no rerolled | Pendiente de implementar/verificar |

## Método y criterios

Usar personaje y almacenamiento de prueba aislados. Registrar identidad de instancia, versión, estado inicial, petición, respuesta decodificada y estado durable final. Controlar reloj y RNG en los casos deterministas. Ejecutar límites de ownership, sesión obsoleta, índices/UID inválidos y payload truncado donde apliquen.

Repetir operaciones confirmadas y cortes alrededor del commit/ACK; ninguna repetición puede duplicar consumo, recompensa o efectos. Verificar observadores y reconexión cuando el caso sea multijugador. La prueba gráfica confirma integración, mientras la fixture de protocolo debe fallar si cambian layout o semántica.

Invariante: Propiedades pertenecen a una unidad; reintento no vuelve a sortear; consumo/reembolso y modificación se confirman juntos.

Registrar cada caso como PASS, FAIL o NO EJECUTADO, con evidencia. No convertir una omisión, un click optimista o un resultado de otro snapshot en PASS.

## TLS de identificación en candidata aislada

El smoke `server/tools/candidate_shard_identification_socket_smoke.py` pasó en la candidata `wakemu-identification-candidate:20261007` (SHA `130ec9fd`) y una base desechable. Comprueba el request nativo 13787 y el resultado 13766 para la regla local, una sola deducción de kamas configurada para el smoke, repetición de la misma respuesta y reconexión con ProtoShard en campo52/`vA`. El costo7 se fijó solo en esa base de prueba. Smoke separado de combate/inventario también pasó. Esto no valida visualmente la ventana ni constituye despliegue.

## Prueba manual — desplegada130ec9fd

En el mundo activo, usa los comandos existentes de chat general:

1. Para el rechazo por nivel, usa Adael, de nivel inferior a60 y ejecuta `!item 12 1` (Laminadora, plantilla nativa de nivel60). Abre el inventario y solicita identificación sobre esa unidad. Debe recibirse `TOO_HIGH_LEVEL` (13766 status2); el objeto permanece y no se crea recibo, engaste ni cargo.
2. Para el éxito, selecciona el personaje existente `Audiluna` (nivel suficiente) y ejecuta `!item 2869 1` (Espada Mento, plantilla nativa de nivel80). Solicita identificación sobre esa unidad. Debe mostrar resultado exitoso, con1–3 casillas vacías, y conservar las propiedades elementales existentes. No uses Adael3 como personaje de prueba para este objeto.
3. Cierra y reabre el inventario; luego reconecta. Debe seguir siendo la misma unidad, con las mismas casillas/colores y sin cargos adicionales. Si se repite el request por retry, la respuesta 13766 debe ser idéntica y no debe aparecer otro recibo.

La cantidad/colores salen de una política local versionada y pueden variar entre unidades; no se espera un resultado aleatorio específico. El costo de esa política en la configuración habitual es0. El smoke de servidor fijó costo7 únicamente para demostrar que el primer commit cobra una vez y el retry no vuelve a cobrar. No se solicita cambiar hechizos, combate ni generar esquirlas durante esta prueba.
