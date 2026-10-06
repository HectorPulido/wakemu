# Implementación de E02 — recuperación de inventario

## Cambio del servidor

13713 contiene `actor_id:i64 + formato:u8 + sección BAGS`. Se utiliza el formato nativo `eHf.BAGS`, ordinal **35**, que contiene exclusivamente `eHe.BAGS`. Antes faltaba ese discriminador y el cliente interpretaba el primer byte del número de bolsos como otro formato de entidad.

Los rechazos de equipar/quitar bolso, consumir, destruir y transferir recargan bolsos y objetos desde la transacción confirmada. La recarga conserva los demás campos de la sesión, incluyendo salud, posición e instancia. No reconstruye una entidad completa ni reaplica hechizos, XP o equipamiento.

## Evidencia y pruebas

- Bytecode: `cwY13713` lee el actor y entrega el resto a `chK`; este llama a `biB.as`, heredado de `eGj`, y finalmente a `eHd.ew`. Este último lee el formato antes de sus secciones.
- `eHf.BAGS` selecciona únicamente `eHe.BAGS` (lector `oY`). No se eligió el encabezado por intuición.
- Nueve pruebas: `PYTHONPATH=server python3 -m unittest server.tests.test_inventory_resync server.tests.test_inventory_bags server.tests.test_inventory_move -q`: **PASS**.
- Regresión: equipar un bolso de cantidad3 es rechazado sin pérdida; recuperación incluye el stack confirmado aunque la sesión tenga inventario viejo, y mantiene HP, XP, posición e instancia.
- Lector Java nativo sobre un snapshot con objetos: **PASS actor=1 format=BAGS sections=1 remaining=0**. Herramienta y payload privados en `.runtime/local/`.

## Pendiente

Validación visual de rechazo y continuación de operaciones en un personaje de auditoría. El lector nativo confirma el formato y consumo completo; no acredita por sí solo la actualización de widgets. El cliente de auditoría anterior no está activo. E02 permanece implementado, pendiente de esa aceptación.

Actualización: issue23 implementa ahora la separación automática de una unidad para bolsos ordinarios en slot libre. La regresión de recuperación usa un slot ocupado para provocar el rechazo; la aceptación visual sigue pendiente.

## Regresión de operaciones rechazadas

Suite ampliada: `PYTHONPATH=server python3 -m unittest server.tests.test_inventory_resync server.tests.test_inventory_bags server.tests.test_inventory_move server.tests.test_inventory_actions server.tests.test_inventory_consumables -q`: **16 pruebas PASS**.

Se ejercitaron rechazo de destrucción de UID inexistente, consumo durante combate y traslado fuera de capacidad. Después de cada rechazo, el snapshot recargado conserva el stack íntegro y su sección BAGS coincide con la persistencia. Son pruebas de servicios y codec; la integración visual del dispatcher continúa pendiente.
