# Orientación: cotejo actualizado y pruebas

## Causa comprobada

`combat_orientation.apply()` rechaza cualquier fase distinta de `active` antes de autorizar al actor. Se ejecutaron **8 casos independientes**: los cardinales 1/3/5/7 en colocación fueron rechazados sin cambiar orientación, contador, posición, AP ni MP; en fase activa fueron aceptados y emitieron 13494 + 13420, sin coste. [Estados y hashes](probe-fases-orientacion.json). Esta prueba alcanza el código de producción, pero no es una reproducción GUI.

## Contrato del cliente

Inspección offline de `dbh`: su frame contiene `fightPlacement` y construye `coZ` para cuatro órdenes de orientación; utiliza el actor seleccionado `okp` o el personaje local si no existe selección. Por tanto, la solicitud también existe durante colocación. `dbl` la utiliza en turno activo.

Se ejecutó el encoder nativo para actor -7: categoría 3, opcode **13655**, cuerpo i64 actor + byte dirección. Los cuatro valores fueron **7,5,1,3**, correspondientes a `aAS.dyA/dyy/dyu/dyw`. Ejemplo dirección 7, frame completo: `00000010033557fffffffffffffff907`. No se han atribuido puntos cardinales nominales sin comprobar sus vectores.

## Sincronización que debe resolverse

`placement_positions()` produce 13652 con posiciones y bandera immediate: **no lleva dirección**. Agregar orientación a sus bytes rompe el contrato. La ruta actual de 13655 envía las respuestas únicamente por la conexión que hizo la solicitud; no prueba sincronización con otros participantes o espectadores. El comienzo asigna 0 a personajes controlados y 3 a NPC durante el bootstrap inicial; debe distinguirse esa inicialización del momento posterior en que el usuario elige orientación.

## Solución concreta de servidor

Separar `placement` de `active`: en colocación comprobar pertenencia del actor al solicitante, encuentro y equipo, edición abierta y revisión compatible con listo/inicio. No exigir turno actual ni eliminar esos controles de la rama activa. Registrar facing en el estado del encuentro; publicar el carrier nativo de orientación a sus observadores autorizados y preservar facing al iniciar y reconstruir la sesión.

Antes de elegir 13494 como carrier de colocación debe verificarse su consumidor y scheduler en esa fase: la validez del parser y su uso activo no acreditan que funcione antes de empezar turnos. Tampoco usar 13530 de posición del mundo como sustituto. Cancelación, listo simultáneo y reinicio deben dejar el encuentro consistente, sin ACK pendiente inventado ni gasto de recursos.

## Validación y límites

`PYTHONPATH=server python3 -m unittest tests.test_combat_orientation`: **3 pruebas aprobadas**. Cubren fase activa, rechazos y bytes; el rechazo de colocación es el comportamiento defectuoso actual, no una aceptación del requisito. Pendientes: carrier consumido en colocación, orientación de actor secundario propio, dos participantes, espectadores, listo/inicio y restauración. Hechizos no intervenidos; issue abierto y sin fixes.
