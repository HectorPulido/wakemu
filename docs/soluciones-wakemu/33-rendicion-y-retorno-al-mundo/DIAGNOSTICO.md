# Diagnóstico — 33

## Contexto registrado

**Confirmado en registros:** a las `2026-10-04T16:03:31Z` (personaje 11, combate 92349904) y `16:21:34Z` (personaje 7, combate 193472141) se registra `combat_abandoned_waiting_return`. Aproximadamente 450–486 ms después llegan solicitudes `12925` de cinco bytes y se rechazan con `Abandon continuation must confirm native loss`. Hay otro rechazo equivalente el 3 de octubre. Esto es evidencia de la continuación fallida, no una reproducción gráfica nueva realizada en esta revisión.

**Causa delimitada:** `combat_abandon.py::prepare` marca fase `finished`, limpia ACK/pending y emite `12238`/flush, pero la sesión conserva `fight`, `fight_messages` y la reserva del grupo hasta completar `12925`. `return_to_world` exige que `combat_results.continuation` devuelva verdadero: ID propio y flag final `1`. El error registrado demuestra que la continuación pasó validación de longitud/ID/flag, pero devolvió falso (flag `0`). El catch solo registra el rechazo; no libera el estado. El inicio de combate exige `fight is None`, por lo que el bloqueo posterior queda explicado en el servidor. La ruta específica del zaap necesita correlación adicional; no atribuir todos los transportes a un mismo handler sin captura.

**Posible solución del servidor:** comprobar la semántica nativa del flag en la secuencia emitida por abandono y hacer que la continuación de un abandono ya autorizado dependa de esa transición propia, conservando ID/propiedad y sin aceptar resultados de combate ajenos. No invertir el flag globalmente: también lo usa el cierre normal. Diseñar finalización idempotente que libere reserva, estado de sesión y pertenencia al mundo incluso ante fallos recuperables, con recuperación explícita si falta continuación. No conceder XP, kamas ni drops al abandonar ni forzar un cambio de mapa arbitrario.

**Validación:** abandono en colocación/turno/ACK pendiente, continuación real con flag observado, solicitud duplicada, ID ajeno, desconexión y reconexión. Después se puede iniciar otro combate y usar transporte; HP persistido y grupo disponible, sin recompensa ni liberación doble. El test actual rechaza explícitamente flag `0`: que pase no acredita compatibilidad con el cliente observado.

## Lectura actual

El codec admite flags 0 y 1 y retorna bool(flag). El caller de abandono exige verdadero: rechaza el 0 observado. Corregir la máquina de estados del cierre, no aceptar cualquier paquete sin validar identidad.

El contexto anterior conserva la evidencia del informe; puede describir una instancia o snapshot anterior. El [cotejo](COTEJO.md) identifica el código leído hoy y sus límites.

## Qué falta para confirmar el recorrido

- Semántica exacta delflag en las ramas nativas usadas.
- Reproducción gráfica nueva y request del transporte que queda bloqueado.
- Política de timeout/rejoin y abandono parcial multiplayer.

## Evidencia de origen

[Informe completo](../../reports/auditoria-problemas-wakemu-2026-10-04.md). No se copian capturas privadas, bases, credenciales ni archivos del cliente.
