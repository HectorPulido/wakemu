# Diagnóstico — 20

## Contexto registrado

**Confirmado parcialmente:** el movimiento ya limita la búsqueda a ubicaciones con jugadores y exige proximidad. Sin embargo, `grow_planted_resources` madura recursos persistidos globalmente y su comentario permite crecer tras desconectar al plantador; respawn tampoco exige jugadores. No existe el sistema de población solicitado.

**Posible solución:** activación por zona/instancia con jugadores presentes, población inicial pequeña por familia y límites. Pausar movimiento, reproducción y demás simulación acordada sin jugadores; definir si al regresar se recupera tiempo o se reanuda sin avance. **Validación:** comparar zona ocupada y vacía, reiniciar solo en una prueba autorizada y comprobar que no reaparece un lote duplicado.

## Lectura actual

Filtra jugadores por mapa/instancia y retorna si no hay ninguno. Eso limita movimiento, pero no es una política completa de reproducción, envejecimiento o suspensión del mundo.

El contexto anterior conserva la evidencia del informe; puede describir una instancia o snapshot anterior. El [cotejo](COTEJO.md) identifica el código leído hoy y sus límites.

## Qué falta para confirmar el recorrido

- Cantidad inicial por familia/zona y caps.
- Definición de subzona/instancia y presencia válida.
- Confirmación sobre pausa del crecimiento vegetal y recuperación de tiempo.

## Evidencia de origen

[Informe completo](../../reports/auditoria-problemas-wakemu-2026-10-04.md). No se copian capturas privadas, bases, credenciales ni archivos del cliente.
