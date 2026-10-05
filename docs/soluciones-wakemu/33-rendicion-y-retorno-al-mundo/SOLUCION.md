# Solución propuesta — 33

Finalizar abandono una vez y liberar sesión/grupo aun con continuación nativa flag 0 observada.

Leer primero [COTEJO.md](COTEJO.md). Estos pasos son una especificación para implementar y validar; no describen una corrección aplicada.

## 1. Reproducir secuencia observada

Usar fixture propia y 13952→12238→12925. Logs históricos muestran 12925 válido de 5 bytes con flag 0 y rechazo La continuación de abandono debe confirmar la semántica nativa de derrota; reservar ID/owner/phase antes/después. Falta correlacionar transportes específicos, no culpar a todos los zaaps sin frame.

## 2. Interpretar flag por ruta

Inspeccionar handler nativo del payload emitido y semántica de flag según fin normal o abandono. No invertir continuación global ni aceptar todo 0 para todos fights. Abandono autorizado ya tiene estado terminal propio que debe determinar si puede limpiarse.

## 3. Diseñar transición terminal idempotente

Estados propuestos abandon_prepared→cleanup_sent→world_returned; recibo por fight/owner/revisión. Persistir HP real, winnernone/no rewards, limpiar pending/ACK y crear outbox. Validar ID/ownership/lease incluso cuando flag sea distinto al de derrota normal.

## 4. Liberar todas las referencias

Finalizador compartido libera reserva de NPC, membresía de combate, fight/fight_messages de la sesión, checkpoint y presencia fuera de combate en orden recuperable. Duplicados no liberan un grupo de otro fight. Abandono parcial 14 se trata por participante, no terminar a todos por un único participante controlado heredado.

## 5. Recuperar si falta continuación

Timeout/disconnect usa recibo y fase terminal para cleanup seguro, no espera eterna. La política debe evitar lanzar otro combate mientras una transición parcial siga mutando estado. Recovery diferencia daño persistido de vida artificial, sin teleportar arbitrariamente.

## 6. Aceptar acción posterior

Después de retorno pedir combate nuevo y transporte real capturado, comparar HP/grupo/wallet. Repetir 12925 y 13952 con mismos/otros IDs; mantener fin normal y flags comprobados. Tests verdes que rechazan 0 no validan el caso real.

## Cierre y recuperación

Aplicar las barreras de [TRANSVERSALES.md](../TRANSVERSALES.md): validar antes de mutar, conservar recibos y revisiones, y confirmar durabilidad antes de respuestas que anuncien cambios de valor. Ensayar fallo antes del commit, después del commit y antes del ACK. Si hay una migración, probar compatibilidad sobre copias y definir recuperación antes de habilitarla. No revertir a un estado anterior que pierda mutaciones ya confirmadas.

## Aceptación

Abandonar no concede XP/kamas/drop; toda reserva y referencia de sesión quedan liberadas una vez.

Completar la matriz de [PRUEBAS.md](PRUEBAS.md), resolver los faltantes bloqueantes y registrar los bytes/estados esperados antes y después. No dar por cerrado el issue por una mejora visual aislada.
