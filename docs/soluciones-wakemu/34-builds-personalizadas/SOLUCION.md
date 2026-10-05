# Solución propuesta — 34

Completar desbloqueo, hojas, guardado, activación autoritativa, estadísticas/deck y persistencia de builds.

Leer primero [COTEJO.md](COTEJO.md). Estos pasos son una especificación para implementar y validar; no describen una corrección aplicada.

## 1. Reproducir y separar las operaciones

Usar un personaje de prueba de nivel 100. La secundaria anunciada antes de guardarla tiene metadata, pero el registro de equipo no contiene su índice; el panel obtiene un modelo nulo. Con cuatro hojas guardadas el panel abre. El ensayo gráfico de activación emitió 13776 y el servidor lo rechazó por falta de handler. Guardar, seleccionar una fila y activar son operaciones distintas.

## 2. Definir un catálogo único de builds

El desbloqueo nativo comprobado es nivel 51 (`eRg.dO` oculta hasta 50). Verificar que las rutas de XP y comando notifican esa transición. El catálogo debe entregar los mismos índices a metadata, equipo, aptitudes y decks; una build vacía necesita hojas válidas, no referencias ausentes. El cupo nativo es 24 builds no permanentes, configuración 2510; no es un límite de tres índices. El índice 3 funciona en el modelo nativo probado. Sustituir la validación artificial 0–2 por un catálogo coherente con ese contrato.

## 3. Persistir la selección autoritativa

Proponer active_build_index y una revisión, con migración de personajes antiguos a 0. Validar que el índice seleccionado existe y pertenece al personaje. Cargarlo antes de calcular estadísticas y preservarlo en el journal y el flush. Guardar una hoja no debe activarla implícitamente.

## 4. Implementar cada contrato nativo por separado

Mantener guardar 12772 y su respuesta 12284. La activación 13776 se confirma con 13811: i64 de personaje y un byte de índice (9 bytes), probado en `ctV` y seguido hasta `eQX.R`/`eQW.QT`. No hay campo de estado; `ctV.dp=false` no representa rechazo. Emitir la confirmación solo después de persistir la activación y verificar aparte el manejo de rechazo y liberación de `heroBuildLock`. Borrar 13169 usa la notificación 12837 de borrado, que no es un ACK de activación. Validar identidad, sesión, fase, índice y revisión antes de mutar.

## 5. Unificar estadísticas y deck efectivo

Usar una sola resolución de equipo, aptitudes y deck desde la build activa. Ready e inicio de combate deben fijar una revisión del conjunto; los casts posteriores validan contra ese snapshot. Sustituir las lecturas fijas del índice 0 donde corresponda. Recalcular desde valores base, evitando acumulación de bonus y curación gratuita al alternar.

## 6. Hacer atómica la progresión de nivel

El caso E06 demuestra que una hoja fija de nivel 49 puede invalidarse después de confirmar nivel 50. Validar todas las hojas, XP, salud y efectos antes del commit, o migrarlas según una política explícita de modulación. No ampliar la aceptación a cualquier nivel para ocultar el fallo. Probar la misma regla en la hidratación del journal y en recompensas.

## 7. Alinear creación, borrado y cupos

Registrar la nueva hoja en todas las colecciones. Preservar los UID de equipo: borrar una build elimina referencias, no los objetos. Definir fallback al borrar la activa y protección de la predeterminada. Interpretar blobs vacíos según el contrato probado; no confundir omisión, hoja vacía válida y colección inexistente.

## 8. Aceptar con un recorrido gráfico y de recuperación

Crear dos secundarias, editarlas, alternar activación, verificar la selección efectiva al entrar en combate, reconectar y repetir tras flush. Comparar interfaz, bytes decodificados, selección persistida y autoridad del encuentro. Las pruebas de guardado existentes no certifican activación, borrado o selección efectiva de una secundaria. Las pruebas de hechizos quedan a cargo de la otra sesión.

## Cierre y recuperación

Aplicar las barreras de [TRANSVERSALES.md](../TRANSVERSALES.md): validar antes de mutar, conservar recibos y revisiones, y confirmar durabilidad antes de respuestas que anuncien cambios de valor. Ensayar fallo antes del commit, después del commit y antes del ACK. Si hay una migración, probar compatibilidad sobre copias y definir recuperación antes de habilitarla. No revertir a un estado anterior que pierda mutaciones ya confirmadas.

## Aceptación

Metadata, equipo, aptitudes, deck y selección comparten índice y revisión; el check visual Activa no prueba autoridad del servidor.

Completar la matriz de [PRUEBAS.md](PRUEBAS.md), resolver los faltantes bloqueantes y registrar los bytes/estados esperados antes y después. No dar por cerrado el issue por una mejora visual aislada.

## Revisión posterior a tus respuestas

[Desbloqueo 51, cupo no permanente 24 y respuesta 13811 verificados](REVISION-RESPUESTAS.md). Esta revisión sustituye las dudas anteriores sobre esos contratos. Las referencias a casts son históricas o trabajo de otra sesión; no se continúan aquí.
