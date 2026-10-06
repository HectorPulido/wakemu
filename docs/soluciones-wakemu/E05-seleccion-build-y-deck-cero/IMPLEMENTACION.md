# E05 — selección persistida (avance parcial)

La autoridad de selección se almacena en `character_build_selection`, con personaje único, índice0–127 y revisión no negativa. El estado inicial es0/revisión0. Store devuelve `active_build_index` y `build_selection_revision` antes de aplicar el overlay del journal; así sus consumidores de estadísticas pueden leer el índice autoritativo.

El bootstrap `build_set` codifica la selección cargada en lugar de fijar0. Seleccionar una hoja ausente falla explícitamente, sin sustituirla silenciosamente. La selección no se obtiene del metadata de guardar una hoja.

Prueba de persistencia: selección1/revisión1 guardada en DB, reapertura y campo protobuf activo1; índice127 sin hoja rechaza carga. Suite:52 casos, **41 PASS y11 SKIP** sin URL Redis en este comando.

Pendiente: método transaccional de activación con lease, handler13776/ACK13811, conservación de HP, journal y sincronización de decks. No se modificó el motor de hechizos; la selección de su deck deberá coordinarse con la otra sesión. Estos cambios aún no se cargaron en el proceso Docker del juego.

## Transición transaccional implementada

`Store.activate_build` valida lease y personaje seleccionado, catálogo, índice y fase antes de mutar. Selección, revisión, HP/máximo y baseline de regeneración se actualizan dentro de la misma transacción SQL. Cambio conserva HP absoluto (recortado al máximo nuevo), sin curación. Repetir selección actual es idempotente y no incrementa revisión. Combate, hoja ausente y generación reemplazada rechazan sin alterar la selección.

Prueba: activar1 con7 HP, repetir, rechazar índice127 inexistente/activación durante combate/sesión reemplazada y reabrir DB conservando selección1 y7 HP. Suite53 casos: **42 PASS y11 SKIP**.

Pendiente: integración13776, consumidores nativos, pruebas con hojas de máximos distintos y Redis real, deck y UI. La existencia del método no acredita todavía activación desde el cliente.

## Salud y Redis real

Regresión ejecutada con journal pendiente: máximo116→110→116 conserva100 HP; con115 HP recorta a110 y volver a116 mantiene110; con0 HP cambiar de hoja no revive. Checkpoint y reapertura SQL conservan selección1, HP0 y máximo110.

Suite Docker con Redis temporal aislado:56 casos, **55 PASS y1 SKIP** de inyección de fallo. Se ejecutó con `WAKFU_MAX_CHARACTERS=5` solo en el proceso de tests: la primera ejecución heredó24 del servicio y falló una prueba que esperaba rechazo del sexto personaje. No fue un fallo de activación. Contenedor Redis temporal eliminado.

Este resultado sustituye el pendiente de máximos distintos y Redis real. Continúan pendientes interfaz, efectos locales y sincronización de deck. El proceso del juego no se reinició durante estas pruebas.
