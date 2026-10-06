# E04. Activación 13776 sin handler

Implementar activación nativa de build como transición propia, con rechazo seguro.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Solución](SOLUCION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Estado y alcance

**Resuelto y verificado:** activación, alternancia, reapertura y edición persistente comprobadas por el usuario; gate PostgreSQL/bootstrap de 44 pruebas. El diagnóstico anterior conserva el estado histórico; ya no describe la ausencia de `13776`.

El dispatcher decodifica actor/índice, rechaza otro personaje y llama a `Store.activate_build`. Store bloquea personaje y lease, valida catálogo y ausencia de combate, y confirma selección, revisión y salud en una transacción PostgreSQL. El éxito envía `13811` y el snapshot de progresión; un rechazo de validación reenvía la selección vigente. Repetir la selección es idempotente. Esto no demuestra que todos los consumidores de combate utilicen el deck seleccionado: esa integración pertenece a E05 y a la sesión de hechizos.

Gate actual `test_build_capacity test_builds test_combat_ready`: **40/40 pruebas**, PostgreSQL aislado, 7,876 segundos. La regresión ejecuta la rama real extraída de `13776`: éxito con `13811` y snapshot `13046`, revisión estable al repetir, estado durable al reabrir Store y serialización de builds. Actor ajeno, índice inexistente, combate y lease obsoleto emiten únicamente la selección vigente y conservan build/revisión/HP. No se modificaron hechizos ni decks. Falta el recorrido visual de activación/rechazo para cerrar E04.

## Evidencia manual del 6 de octubre de 2026

El usuario creó dos builds adicionales en Audiluna, activó una y alternó la selección correctamente. Después de cambiar de personaje y volver, el botón «Modificar las características» no abrió la ventana. La activación visual queda comprobada; la reapertura y la selección restaurada siguen sin validación. No se cerró completamente el proceso cliente: el usuario no dispone de las credenciales de la cuenta de auditoría. No confundir esta prueba con un login nuevo. Se pidió comprobar apertura de inventario y movimiento después del botón para delimitar si el bloqueo afecta solo a builds o a la interfaz general. No se reinició el servidor durante estas pruebas.

## Causa de la reapertura fallida y corrección en fuente

El log del cliente de auditoría registra `openCloseAptitudes` → `byp.dRr` → `byn.<init>` y `NullPointerException`: `jFK` es null al llamar `bQk.elU()`. `bhp.dkV()` busca el modelo del deck por índice activo; `bhp.dkJ()` construye ese registro desde los decks de `fzh`. El servidor publicaba builds 1 y 2, pero `deck_collection()` omitía sus decks vacíos. PostgreSQL confirmó ambos valores vacíos y los logs confirmaron activación 1→0→1 antes de reentrar. Inventario y movimiento siguen funcionando; el click fallido no emite petición al servidor.

La corrección en fuente publica una entrada para cada índice del catálogo, conservando decks guardados y usando el mismo `default_deck(character)` que la respuesta de guardado para hojas vacías. No modifica hechizos ni efectos. Regresión y despliegue de esta corrección pendientes; no declarar resuelta la reapertura antes de comprobarla en cliente.

## Dependencias

34, E05, E06, E08. Ver el [índice general](../README.md) y las [reglas transversales](../TRANSVERSALES.md).

## Invariante de aceptación

El check optimista del cliente se confirma por servidor o se revierte con un mensaje probado.

## Revisión posterior a tus respuestas

[Desbloqueo 51, cupo no permanente 24 y respuesta 13811 verificados](REVISION-RESPUESTAS.md). Esta revisión sustituye las dudas anteriores sobre esos contratos. Las referencias a casts son históricas o trabajo de otra sesión; no se continúan aquí.

## Regresión y recarga de la corrección

Gate `test_builds test_build_capacity test_combat_bootstrap`: **44 pruebas OK**, PostgreSQL aislado. La regresión guarda hojas 1/2, conserva un deck no predeterminado en 1, resuelve el vacío de 2, activa 1, reabre Store y decodifica el registro 0/1/2 y la selección13811 exacta. El 6 de octubre se recargó world con el archivo fuente montado; boot `5485e527a14848ecaf55a3634f464c96`, listener15556 confirmado y Docker healthy. La imagen construida antes de este parche conserva la versión anterior del archivo; la ejecución actual usa el montaje fuente. Falta validación visual de reapertura.

## Validación manual posterior a la corrección

El usuario confirmó los cuatro pasos: entrar con Audiluna, abrir características, encontrar ambas hojas con «rueba auditoría» activa, cambiar de personaje y volver a abrir correctamente. Además creó una tercera build, la seleccionó, salió y volvió; editó sus datos y confirmó que se conservaron, con reiniciada incluida según su reporte. Esto cierra el fallo de reapertura y la activación visual de E04 junto con el gate44. E05 mantiene pendiente la selección consistente en los consumidores de combate; no atribuir esa cobertura a esta prueba.
