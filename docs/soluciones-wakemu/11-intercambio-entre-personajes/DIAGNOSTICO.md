# Diagnóstico — 11

## Contexto registrado

**Pendiente:** no se encontró un servicio de intercambio integrado en el dispatcher.

**Posible solución:** invitación/aceptación, oferta revisada, confirmación de ambas partes y transferencia atómica bajo leases. Cancelar por desconexión o cambio de oferta. **Validación:** dos clientes, cancelación, falta de espacio y ausencia de pérdida/duplicación.

## Lectura actual

Este movimiento valida inventario propio; no constituye intercambio bilateral. Trade necesita dos propietarios, consentimiento y confirmación atómica, conservando UID y propiedades.

El contexto anterior conserva la evidencia del informe; puede describir una instancia o snapshot anterior. El [cotejo](COTEJO.md) identifica el código leído hoy y sus límites.

## Qué falta para confirmar el recorrido

- Protocolos/ACK completos y restricciones de distancia/combate.
- Política de items ligados, UIDs transferidos y offers de stacks.
- Autoridad transaccional elegida y recuperación entre Redis/SQL.

## Evidencia de origen

[Informe completo](../../reports/auditoria-problemas-wakemu-2026-10-04.md). No se copian capturas privadas, bases, credenciales ni archivos del cliente.
