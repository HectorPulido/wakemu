# Diagnóstico — 7

## Contexto registrado

**Pendiente:** las rutas de plantación y recolección revisadas no calculan ni persisten deltas personales de Wakfu/Stasis. El bootstrap ecológico de `maps/planting_context.py` sincroniza familias y poblaciones, lo cual no equivale a progresión personal.

**Posible solución:** estado propio persistido, política de acciones ecológicas y mensajes de actualización. Validar las reglas antes de asignar signo o cantidad. **Validación:** plantar/cosechar con diferentes estados de población y conservar el valor al reconectar.

## Lectura actual

Este commit confirma plantación y consumo; agregar progreso ecológico requiere una regla y un recibo en la misma autoridad. No se puede certificar el cálculo de Wakfu/Stasis por observar crecimiento.

El contexto anterior conserva la evidencia del informe; puede describir una instancia o snapshot anterior. El [cotejo](COTEJO.md) identifica el código leído hoy y sus límites.

## Qué falta para confirmar el recorrido

- Fórmula/rangos y límites de Wakfu/Stasis para esta versión.
- Codec del valor personal y periodicidad de publicación.
- Reglas de atribución al plantar, cosechar y destruir.

## Evidencia de origen

[Informe completo](../../reports/auditoria-problemas-wakemu-2026-10-04.md). No se copian capturas privadas, bases, credenciales ni archivos del cliente.
