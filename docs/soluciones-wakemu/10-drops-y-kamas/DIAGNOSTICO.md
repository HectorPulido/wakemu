# Diagnóstico — 10

## Contexto registrado

**Confirmado:** los kamas de combate también valen cero por defecto. `combat_rewards.py` y `combat_results.py` declaran que no generan loot.

**Posible solución:** configurar una política de kamas e implementar tablas de botín, tiradas, inserción de objetos y recibos de entrega en una transacción idempotente. **Validación:** resumen y wallet coinciden; el loot permanece al reconectar y no se duplica.

Dejar configurable un "multiplicador de drop y kks"

## Lectura actual

Ya existe entrega transaccional con recibo. Reutilizar esa barrera al incorporar tablas de drop; no añadir concesións independientes que puedan duplicarse tras reconexión.

El contexto anterior conserva la evidencia del informe; puede describir una instancia o snapshot anterior. El [cotejo](COTEJO.md) identifica el código leído hoy y sus límites.

## Qué falta para confirmar el recorrido

- Tablas de loot verificadas por familia y fórmula de kamas.
- Semántica de multiplicador de drop, caps y reparto.
- Política de inventario lleno, recompensa pendiente y equipo identificado.

## Evidencia de origen

[Informe completo](../../reports/auditoria-problemas-wakemu-2026-10-04.md). No se copian capturas privadas, bases, credenciales ni archivos del cliente.
