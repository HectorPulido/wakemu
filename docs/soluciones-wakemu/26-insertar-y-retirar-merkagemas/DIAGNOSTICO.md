# Diagnóstico — 26

## Contexto registrado

**Confirmado parcialmente:** `items/haven_bag_store.py::rearrange_rooms` mueve/intercambia gemas ya existentes y declara que no crea objetos de inventario. Existe habitación inicial y edición de mobiliario, pero no se observó transferencia completa inventario → ranura de gema.

**Posible solución:** insertar/retirar gemas propias con validación de UID/tipo, consumo/devolución y actualización transaccional de habitación y mapa. **Validación:** habitación habilitada, persistencia, retirada y protección de la gema fija inicial.

## Lectura actual

La disposición existente trabaja sobre gemas ya disponibles. Añadir una merkagema requiere consumo desde inventario y autoridad del merkasaco; no basta reordenar habitaciones.

El contexto anterior conserva la evidencia del informe; puede describir una instancia o snapshot anterior. El [cotejo](COTEJO.md) identifica el código leído hoy y sus límites.

## Qué falta para confirmar el recorrido

- Solicitudes/ACK de insert/remove y comportamiento primario/secundario.
- Reglas de retirada con muebles/plantas/visitantes y gema fija.
- Asignación UID estable de gemas iniciales y migration de layouts viejos.

## Evidencia de origen

[Informe completo](../../reports/auditoria-problemas-wakemu-2026-10-04.md). No se copian capturas privadas, bases, credenciales ni archivos del cliente.
