# Diagnóstico — 8

## Contexto registrado

**Confirmado:** `storage/profession_store.py` guarda oficio y nivel, sin XP; su encabezado declara ausencia de curva/progresión. La ruta de plantación no concede XP. `docs/reports/ecosistema.txt` documenta el paquete `12916` como delta de XP de oficio.

**Posible solución:** persistir XP, curva y nivel; conceder la recompensa una sola vez por acción completada y emitir su delta. El ejemplo capturado de +100 no es una fórmula universal. **Validación:** progreso inmediato, subida de nivel, reconexión y cancelación sin recompensa.

## Lectura actual

El almacenamiento de oficios mantiene nivel, no una curva de XP de oficio. La XP del personaje en progression no sustituye ese dominio ni sus mensajes.

El contexto anterior conserva la evidencia del informe; puede describir una instancia o snapshot anterior. El [cotejo](COTEJO.md) identifica el código leído hoy y sus límites.

## Qué falta para confirmar el recorrido

- Curva nativa por oficio y límites.
- Recompensas por semilla/cosecha/receta y política de fallos.
- Formato exacto de 12916 y actualización de acciones desbloqueadas.

## Evidencia de origen

[Informe completo](../../reports/auditoria-problemas-wakemu-2026-10-04.md). No se copian capturas privadas, bases, credenciales ni archivos del cliente.
