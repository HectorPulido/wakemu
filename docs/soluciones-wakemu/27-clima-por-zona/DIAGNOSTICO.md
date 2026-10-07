# Diagnóstico — 27

## Contexto registrado

**Confirmado:** la tarea `weather` está desactivada en configuración cron y además no está permitida por `GlobalTasks`. Activar el booleano no basta.

**Posible solución:** modelo climático por zona, calendario/transiciones y mensajes; integrarlo después con crecimiento y porcentaje de plantación. **Validación:** cambio visible y misma condición para todos los jugadores de la zona.

## Lectura actual

El servidor ya persiste y publica el estado de clima para territorios configurados. `send_planting_context()` emite el paquete 13948 al entrar y al cambiar de mapa; las reglas de flora consultan el clima exacto de la región. Ahora hay transiciones explícitas SQL, outbox y un callback cron de tick en fuente. Falta re-enviar el snapshot al cruzar una frontera regional dentro del mismo mapa y validar el resultado visual.

El contexto anterior conserva la evidencia del informe; puede describir una instancia o snapshot anterior. El [cotejo](COTEJO.md) identifica el código leído hoy y sus límites.

## Qué falta para confirmar el recorrido

- Semántica completa de los campos de 13948 y parser de previsión 13895.
- Fuente autorizada de valores iniciales para otros territorios; las transiciones existentes son valores explícitos locales, no un generador de calendario oficial.
- Política reloj global versus pausa 20.
- Efectos exactos de calendario sobre plantas y frecuencia de cambios.

## Evidencia de origen

[Informe completo](../../reports/auditoria-problemas-wakemu-2026-10-04.md). No se copian capturas privadas, bases, credenciales ni archivos del cliente.
