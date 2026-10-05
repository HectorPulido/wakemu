# Diagnóstico — E01

## Contexto registrado

La auditoría registró 8.245 eventos plant_growth_error con database disk image is malformed entre 03:13:05Z y 05:33:54Z. Son datos históricos, no prueba de integridad actual de todas las bases. La reproducción del bolso tuvo quick_check correcto; no vincular causalmente ambos hallazgos. No se efectuó reparación.

## Lectura actual

El manejo de conexiones no demuestra integridad física de una base histórica. Se requiere comprobar una copia consistente; no vincular la corrupción histórica con el bolso sin evidencia causal.

El contexto anterior conserva la evidencia del informe; puede describir una instancia o snapshot anterior. El [cotejo](COTEJO.md) identifica el código leído hoy y sus límites.

## Qué falta para confirmar el recorrido

- Archivo/boot exactos de la corrupción histórica y integridad actual.
- Backups disponibles, tiempos yWAL/SHM; journals posteriores.
- Origen físico del daño y alcance de datos perdidos.

## Evidencia de origen

[Informe completo](../../reports/auditoria-problemas-wakemu-2026-10-04.md). No se copian capturas privadas, bases, credenciales ni archivos del cliente.
