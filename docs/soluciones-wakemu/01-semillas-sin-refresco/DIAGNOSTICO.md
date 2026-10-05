# Diagnóstico — 1

## Contexto registrado

**Confirmado:** `server/wakfu_server/maps/planting.py`, función `complete`, resta una unidad en SQLite dentro de la transacción. Envía creación de recurso `13135` y resultado `12954`, sin delta `12470`, porque la implementación asume que el manejador nativo del resultado consume la semilla visualmente. `server/local_game_server.py`, ruta `13429`, envía esos mensajes y actualiza el personaje. El registro contiene resultados aplicados.

**Hipótesis:** el estado persistido cambia, pero el cliente no consume o no refresca el stack con esa secuencia en el caso observado. Los prefijos de `12954` todavía tienen semántica parcialmente interpretada.

**Posible solución:** correlacionar UID, cantidad, solicitud, ocupación y resultado en una captura del fallo. Corregir el contexto o la sincronización según el manejador real; no añadir `12470` sin comprobar si duplicaría el consumo. **Validación:** cantidad correcta inmediatamente, al reconectar y tras repetir el resultado, tanto con una semilla como con un stack.

## Lectura actual

La finalización contiene transacción, recibo y consumo persistido. El defecto visual no implica ausencia del descuento SQL; falta demostrar el contrato de actualización del inventario en la sesión.

El contexto anterior conserva la evidencia del informe; puede describir una instancia o snapshot anterior. El [cotejo](COTEJO.md) identifica el código leído hoy y sus límites.

## Qué falta para confirmar el recorrido

- Referencia y UID de una plantación gráfica reproducida; el ensayo anterior no inició la acción.
- Semántica completa y campos nativos del resultado 12954 que disparan consumo.
- Política de consumo en tirada fallida y cancelación.

## Evidencia de origen

[Informe completo](../../reports/auditoria-problemas-wakemu-2026-10-04.md). No se copian capturas privadas, bases, credenciales ni archivos del cliente.
