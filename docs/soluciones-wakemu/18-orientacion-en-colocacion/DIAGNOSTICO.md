# Diagnóstico — 18

## Contexto registrado

**Confirmado:** `combat_orientation.py::apply` exige fase `active`, turno propio y ausencia de ACK pendiente; por tanto rechaza colocación aunque la solicitud alcance `13655`.

**Posible solución:** ruta específica de orientación durante colocación, con autorización del actor y respuesta apropiada a esa fase. **Validación:** dirección visible antes de listo y conservada al iniciar combate, sin consumir AP/MP.

## Lectura actual

Exige fase active y turno sincronizado; rechaza placement. Para orientación en colocación hace falta una transición distinta con validación de actor y carrier comprobado.

El contexto anterior conserva la evidencia del informe; puede describir una instancia o snapshot anterior. El [cotejo](COTEJO.md) identifica el código leído hoy y sus límites.

## Qué falta para confirmar el recorrido

- Carrier y ACK correctos durante placement.
- Regla de edición después de listo y durante countdown.
- Captura real del clic y orientación deseada.

## Evidencia de origen

[Informe completo](../../reports/auditoria-problemas-wakemu-2026-10-04.md). No se copian capturas privadas, bases, credenciales ni archivos del cliente.
