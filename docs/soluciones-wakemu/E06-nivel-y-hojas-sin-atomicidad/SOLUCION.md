# Solución propuesta — E06

Hacer atómica la transición de nivel/XP/hojas/salud y definir semántica de hojas limitadas.

Leer primero [COTEJO.md](COTEJO.md). Estos pasos son una especificación para implementar y validar; no describen una corrección aplicada.

## 1. Conservar la fixture exacta

Nuevo personaje 49, hoja de índice 0 y aptitudes con nivel 49, luego !nivel 50. Guardar excepción y filas antes/después; reproducir en BD temporal con copia fija y después con checkout actual para distinguir versiones. No modificar el personaje del usuario para probar la corrupción lógica.

## 2. Decidir nivel real versus limitado

Aptitudes.validate admite -1 o nivel actual, mientras deck permite cap inferior. Determinar si nivel fijo 49 representa modulación válida o una hoja real que debía migrar. No ampliar a cualquier nivel sin proteger presupuesto, equipamiento y máximo del personaje.

## 3. Preparar estado destino antes del commit

Calcular XP/nivel, hojas compatibles, presupuestos y salud en una copia canónica; validar todos los evaluadores que se ejecutarán al cargar. Si hay error, conservar nivel y XP anteriores o devolver un rechazo explícito de transición, nunca confirmar primero y fallar recalculando después.

## 4. Persistir por una autoridad definida

En SQL: transacción única de nivel/progresión/hojas/salud. Con Redis: diseñar revision/recibo que coordine hoja pendiente y progreso inmediato; recovery no debe evaluar hoja antigua con nivel nuevo. No declarar atomicidad entre dos sistemas por usar BEGIN en uno de ellos.

## 5. Sincronizar después de confirmar

Compartir servicio de progresión entre recompensa y consola; notificar delta/total y colecciones conforme 9/34. Al repetir command/reward leer recibo y versión sin repetir salud ni recalcular con hoja incompatible.

## 6. Migrar estados ya parciales

Detectar nivel, XP, hoja y HP inconsistentes en copia; reparar según política de nivel limitado elegida, preservando allocations y daño real. Registrar filas afectadas y checks antes/después. Un clamp de HP indiscriminado no soluciona la validación de aptitudes.

## Cierre y recuperación

Aplicar las barreras de [TRANSVERSALES.md](../TRANSVERSALES.md): validar antes de mutar, conservar recibos y revisiones, y confirmar durabilidad antes de respuestas que anuncien cambios de valor. Ensayar fallo antes del commit, después del commit y antes del ACK. Si hay una migración, probar compatibilidad sobre copias y definir recuperación antes de habilitarla. No revertir a un estado anterior que pierda mutaciones ya confirmadas.

## Aceptación

Nivel/XP y hojas compatibles cambian juntos; un evaluador no puede fallar después de dejar media transición confirmada.

Completar la matriz de [PRUEBAS.md](PRUEBAS.md), resolver los faltantes bloqueantes y registrar los bytes/estados esperados antes y después. No dar por cerrado el issue por una mejora visual aislada.
