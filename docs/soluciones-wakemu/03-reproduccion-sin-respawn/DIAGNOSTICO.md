# Diagnóstico — 3

## Contexto registrado

**Confirmado:** el crecimiento crea un grupo con un miembro; respawn recupera grupos derrotados y no equivale a reproducción. `server/cron-service/config.json` desactiva `population`; `storage/global_tasks.py` solo admite callbacks de persistencia.

**Posible solución:** servicio de población con reproducción y ampliación de grupos, límites por zona/familia, ocupación, identificadores únicos y persistencia idempotente. Definir explícitamente una política del emulador si no se dispone de reglas acreditadas. **Validación:** aparecen nuevas unidades sin duplicarlas por reintento y sin crecimiento ilimitado.

No debe haber respawn automatico excepto por mecanicas de reproduccion y siembra

## Lectura actual

El registro permitido contiene flush de posiciones, builds y grupos; population no está entre las tareas admitidas. Activar solamente su configuración no implementa reproducción.

El contexto anterior conserva la evidencia del informe; puede describir una instancia o snapshot anterior. El [cotejo](COTEJO.md) identifica el código leído hoy y sus límites.

## Qué falta para confirmar el recorrido

- Reglas de familia/madurez/sexo y probabilidad.
- Máximos de miembros y población, prioridad ante falta de celda.
- Qué bootstrap existente se conserva al retirar respawn y qué datos históricos migrar.

## Evidencia de origen

[Informe completo](../../reports/auditoria-problemas-wakemu-2026-10-04.md). No se copian capturas privadas, bases, credenciales ni archivos del cliente.
