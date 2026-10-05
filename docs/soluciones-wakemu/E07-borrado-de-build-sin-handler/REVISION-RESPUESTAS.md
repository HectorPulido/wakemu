# E07 — Borrado de builds: contrato nativo y persistencia

## Evidencia actual

El encoder nativo `cnO` emite **13169**, categoría 3, cuerpo **9 bytes**: identidad i64 de personaje e índice signed byte. La respuesta `cnP` consume **12837**, cuerpo **10 bytes**: personaje, índice y byte de **error**. Cero significa éxito; uno significa rechazo, no éxito. Se ejecutaron ambos codecs nativos con personaje sintético 12345/índice 2 y respuestas 0/1: todos conservaron los campos esperados. [Fixture y hashes](probe-contrato-borrado-nativo.json).

El consumidor `cEN` restablece `heroBuildLock` antes de ambas ramas. Con error muestra `build.error.delete.build`; sin error llama `dbU.d(character,index)` y muestra `build.deleted`. Esto identifica una respuesta de eliminación, distinta de guardado 12284 y activación 13811. No se ejecutó ese consumidor dentro de GUI ni se acredita un bloqueo visual nuevo.

No se encontró ruta 13169 en `local_game_server.py`, ni servicio `delete_build` en `Store`. `save_build` persiste las cuatro hojas y actualiza salud; no es una operación de eliminación. `BuildJournal.flush` compara snapshots completos pero solo hace INSERT/UPDATE de índices presentes: quitar un índice de `current` no ejecuta DELETE SQL. Un borrado implementado únicamente en la caché podría reaparecer tras checkpoint/reconexión.

## Solución concreta del servidor

Implementar una transición dedicada con validación de ownership/lease, índice existente, índice protegido por defecto y fase permitida. No destruir objetos referenciados por una hoja: sus UIDs son propiedad del inventario. Rechazar borrado durante combate y responder 12837 con error 1; no dejar la solicitud sin respuesta.

La selección activa debe persistirse primero como autoridad única (issue 34). Para borrar una secundaria activa fuera de combate, resolver y validar la build por defecto antes de mutar: recalcular equipo/aptitudes/salud coherentes y persistir selección y eliminación atómicamente. Si ese fallback no es válido, rechazar sin tocar ninguna hoja. No se usa el simple resaltado de la interfaz como selección activa.

Añadir tombstone versionado o aplicar diferencia de índices baseline/current dentro de la misma transacción de flush, con comparación de baseline y ownership. Si llega un nuevo guardado mientras se confirma el borrado, conservar la revisión nueva; un checkpoint no puede borrar cambios posteriores. Probar caída después del commit y antes del ACK. La operación necesita recibo durable; un retry no debe borrar una build recreada después usando el mismo índice sin distinguir su revisión.

Tras commit duradero enviar 12837 y las colecciones/selección actualizadas que el consumidor real necesita. En todas las salidas restablecer controles mediante su respuesta nativa. No anunciar éxito antes de garantizar que reconectar no resucita las hojas.

## Verificación que falta

Eliminar secundaria activa e inactiva, proteger índice 0, cuenta ajena, sesión sustituida, combate, retry y recreación del mismo índice, Redis caído y flush concurrente. El cotejo estático adicional de `dbU.d` y `eQX.U` se registra a continuación; falta ejecutar ese recorrido con GUI y datos completos. No se implementó ninguna corrección y no se declara completo el recorrido gráfico.

## Profundización del consumidor de éxito

Se inspeccionaron `dbU.d(long,byte)` y `eQX.U(long,int)` directamente del cliente instalado. Antes de eliminar, `dbU.d` obtiene los UIDs de la hoja de equipo y llama a `eQX.U`. Este método valida mediante `eQX.c`, protege índice **0**, exige los cuatro registros y verifica el contexto del personaje. Si la build eliminada coincide con `eQW.wM()` (selección activa), llama a `R(character,0)` y aborta si el fallback no puede aplicarse. Después elimina metadatos (`eQW.QU`), hoja de equipo (`fpl.Wk`), registro de deck (`fzh.aaE`) y aptitudes (`eQJ.QK`). Es inspección de lifecycle, sin editar ni ejecutar hechizos.

Si la ventana pertinente está abierta, `dbU.d` también procesa los UIDs de equipo mediante `fpd.C` y actualiza la selección de edición: vuelve a 0 si se eliminó la fila seleccionada, o conserva otra fila existente. No confundir esa selección de edición con la selección activa aplicada por `eQX.U`.

**Implicación para el servidor:** el ACK de éxito ya dispara la eliminación de las cuatro colecciones locales y el intento de fallback. No enviar además cuatro borrados inventados. Antes del ACK, la autoridad del servidor debe haber confirmado el mismo fallback y su estado efectivo; después debe publicar los carriers nativos de selección/estadísticas que correspondan y mantener el bootstrap consistente. El retorno booleano de `eQX.U` se descarta en `dbU.d`: `cEN` puede mostrar «build.deleted» aunque la validación local haya impedido borrar. Por ello responder éxito a un índice/contexto inválido no garantiza coherencia y no es una solución.

Este análisis resuelve qué colecciones elimina el consumidor. No demuestra que `fpd.C` destruya objetos de inventario: su callback aún necesita trazarse para separar caché de equipo de propiedad; no autoriza borrar UIDs SQL. Dumps privados en `.runtime/local/review-continuacion-20261004/build-delete/`, sin publicar bytecode propietario.

## Cotejo de los objetos referenciados

El callback pendiente quedó trazado hasta la notificación: BootstrapMethods de `dbU` identifica el lambda como `fnR.bYE()`. `dbU.b(fpd,Long)` llama a **`fpd.C(uid)`**, que ejecuta `Map.get` y devuelve Optional; no llama a **`fpd.B(uid)`**, que es la operación distinta con `Map.remove`. `fnR.bYE` obtiene un listener `fnY` desde `fnX.ghu()` y llama a `aI(item)`, sin modificar directamente UID, cantidad ni el mapa de inventario.

Por tanto, la ruta inspeccionada hace lookup y notificación del objeto después de eliminar su hoja, no una eliminación directa del inventario. Falta inspeccionar el listener concreto activo para acreditar todos sus efectos visuales, pero ningún paso observado justifica destruir la unidad persistida. La solución del servidor debe conservar cantidad, UID, contenedor y propiedades al borrar una build; los deltas de inventario solo corresponden a una transferencia real, no a quitar referencias. Esta conclusión procede de bytecode actual, sin clicks, ejecución de hechizos o cambios al cliente.
