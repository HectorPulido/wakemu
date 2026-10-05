# Diagnóstico — 14

## Contexto registrado

**Confirmado parcialmente:** existe `combat_multiplayer_wire.py::decode_join` para `13241`, pero no apareció su conexión al dispatcher. El estado de combate se mantiene en la sesión con variables `fight` y `fight_messages`.

**Posible solución:** registro compartido de combates, resolución del objetivo, validación de fase/equipo/cupos y publicación a todos los participantes. **Validación:** unión durante colocación y rechazo al cerrar la fase, con estado consistente en ambos clientes.

## Lectura actual

Existe codec de join; falta comprobar integración autoritativa con fase, equipo, capacidad y bootstrap del participante. La presencia del codec no prueba ingreso funcional.

El contexto anterior conserva la evidencia del informe; puede describir una instancia o snapshot anterior. El [cotejo](COTEJO.md) identifica el código leído hoy y sus límites.

## Qué falta para confirmar el recorrido

- Formato 13241 completo, respuestas y requisitos de acceso.
- Registro compartido y política de ACK multi-cliente aún no implementados.
- Cupos, reparto de premios y abandono parcial.

## Evidencia de origen

[Informe completo](../../reports/auditoria-problemas-wakemu-2026-10-04.md). No se copian capturas privadas, bases, credenciales ni archivos del cliente.
