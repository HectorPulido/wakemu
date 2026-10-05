# Diagnóstico — 23

## Contexto registrado

**Confirmado:** `inventory_bags.py::equip` rechaza `quantity != 1`; `inventory_bag_rules.py::ordinary` también rechaza bolsos especializados o con criterios. El log registra `Unavailable or unsupported owned bag item` a las `2026-10-03T23:09:14Z`. El handler intenta resincronizar al rechazar.

**Evidencia visual:** la captura muestra “Bolso sadida negro x3 añadido”, UID `1099511628691`, inventario sin celdas y contador `0/0`, mundo negro y ficha con `2.147.483.647` PdV en rojo, mientras el indicador inferior muestra `2274`. El personaje figura en nivel 6. El chat informa mapa 1134, instancia 0 y posición (-19, 15, -8). Esto confirma una inconsistencia de varias vistas, no solo de la cantidad del bolso. La captura no tiene hora y no permite correlacionarla inequívocamente con el evento del registro.

**Hipótesis:** el rechazo de un stack deja cambios optimistas en la interfaz o la respuesta de resincronización invalida/desordena el estado nativo. `inventory_move.py::synchronization` envía `13713` con identidad y `inventory.bags(character)`; revisar ese codec y el orden frente a los mensajes de equipamiento. El valor mostrado de PdV equivale a `INT32_MAX`, compatible con un sentinel/límite o cálculo saturado interpretado como vida, pero no demuestra por sí mismo overflow, corrupción de SQLite ni un error específico de combate.

**Posible solución:** separar una unidad con UID propio dentro de la transacción, equiparla sin destruir el stack restante y restaurar todas las vistas ante rechazo. Evaluar filtros/criterios de esa referencia. Capturar la secuencia inmediatamente anterior y posterior al fallo y verificar el parser real de `13713`, número de contenedores, contenido y actualización de características. **Validación:** stack de 2+, espacio insuficiente, slot ocupado, rechazo y reconexión sin pérdida; inventario conserva capacidad/celdas, mapa sigue visible y PdV de ficha/HUD son coherentes. No se observó evidencia que vincule este evento con la corrupción posterior de SQLite.

**Causa confirmada en la prueba posterior:** la respuesta de rechazo usa `inventory_move.py::synchronization`, que serializa identidad seguida únicamente de `inventory.bags(character)`. El bytecode de `cwY` lee esa identidad y conserva el resto; el handler `chK`, rama `13713`, entrega el resto a `biB.as(byte[])`, deserialización de entidad, no a un lector aislado de bolsas. El cliente interpreta los bytes como secciones de personaje y falla. Detalles y correlación en la sección final. La restricción del stack provoca el rechazo; el payload incorrecto de recuperación es el segundo fallo que rompe el estado visual.

## Lectura actual

13713 se construye con identidad y bags(character). El consumidor observado espera una entidad; el error binario puede corromper el modelo visual aunque SQL permanezca íntegro.

El contexto anterior conserva la evidencia del informe; puede describir una instancia o snapshot anterior. El [cotejo](COTEJO.md) identifica el código leído hoy y sus límites.

## Qué falta para confirmar el recorrido

- Referencia/criterios completos y política de bolsos especializados.
- Codec de recuperación elegido y orden de aplicación sobre entidad ya cargada.
- Semántica de swap con bolso que contiene objetos.

## Evidencia de origen

[Informe completo](../../reports/auditoria-problemas-wakemu-2026-10-04.md). No se copian capturas privadas, bases, credenciales ni archivos del cliente.
