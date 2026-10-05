# Diagnóstico — 2

## Contexto registrado

**Confirmado:** `maps/planting_runtime.py::monster_growth_member` elige una referencia por nivel mínimo y referencia dentro de la familia, priorizando criaturas recolectables. El recurso plantado se transforma en un grupo, pero no se observó un ciclo posterior que cambie edad o referencia del monstruo vivo. El código no demuestra que una referencia de bebé deba convertirse automáticamente en otra.

**Posible solución:** definir y persistir una política de maduración por familia, con referencias compatibles, tiempos y actualización de estadísticas/visualización. Separar crecer una semilla de envejecer un NPC. **Validación:** bebé y adulto antes/después del plazo, conservación al reconectar y comportamiento durante combate.

## Lectura actual

La creación del miembro desde la semilla no implementa una evolución periódica de todos los monstruos ya vivos. Separar germinación de evolución de población.

El contexto anterior conserva la evidencia del informe; puede describir una instancia o snapshot anterior. El [cotejo](COTEJO.md) identifica el código leído hoy y sus límites.

## Qué falta para confirmar el recorrido

- Referencias concretas bebé/adulto y reglas por familia verificadas.
- Tiempo de maduración, HP al crecer y política de especies sin adulto.
- Mensaje nativo para cambiar forma y componentes sin perder identidad.

## Evidencia de origen

[Informe completo](../../reports/auditoria-problemas-wakemu-2026-10-04.md). No se copian capturas privadas, bases, credenciales ni archivos del cliente.
