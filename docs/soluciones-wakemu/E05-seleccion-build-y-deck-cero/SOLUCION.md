# Solución propuesta — E05

Persistir y resolver una sola selección para stats, aptitudes y combate.

Leer primero [COTEJO.md](COTEJO.md). Estos pasos son una especificación para implementar y validar; no describen una corrección aplicada.

## 1. Inventariar todas las lecturas de selección

Buscar active_build_index y acceso get(0) en bootstrap, estadísticas, ready, cast y recuperación. Que un evaluador admita un índice explícito no demuestra que el servidor lo seleccione. Registrar cada consumidor que todavía fuerza 0.

## 2. Diseñar persistencia compatible

Agregar selección y revisión con valor inicial 0 para personajes antiguos. Validar la existencia de la hoja y preservar el índice en SQL, journal y flush. No guardar la autoridad exclusivamente en la conexión.

## 3. Unificar el resolver efectivo

Resolver equipo, aptitudes, deck y nivel desde una misma build. Emitir ese índice en metadata. Editar una hoja secundaria no cambia la activa ni aplica sus bonus.

## 4. Fijar la revisión de combate

Al iniciar, copiar la selección y deck efectivos al encuentro. Los casts consultan ese snapshot, evitando que una edición externa cambie permisos durante el turno. Revisar recuperación de encuentros.

## 5. Validar alternancia y fallback

Alternar dos hojas con equipo y hechizos distintos; comprobar persistencia antes y después del flush. Borrar la activa debe elegir un fallback válido y notificarlo con el contrato probado.

## Cierre y recuperación

Aplicar las barreras de [TRANSVERSALES.md](../TRANSVERSALES.md): validar antes de mutar, conservar recibos y revisiones, y confirmar durabilidad antes de respuestas que anuncien cambios de valor. Ensayar fallo antes del commit, después del commit y antes del ACK. Si hay una migración, probar compatibilidad sobre copias y definir recuperación antes de habilitarla. No revertir a un estado anterior que pierda mutaciones ya confirmadas.

## Aceptación

El mismo índice y revisión determinan todas las hojas y el encuentro; ningún consumidor fuerza 0 por omisión.

Completar la matriz de [PRUEBAS.md](PRUEBAS.md), resolver los faltantes bloqueantes y registrar los bytes/estados esperados antes y después. No dar por cerrado el issue por una mejora visual aislada.
