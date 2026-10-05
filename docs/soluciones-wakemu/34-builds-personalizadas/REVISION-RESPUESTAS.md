# Revisión nativa posterior a las respuestas

## Desbloqueo resuelto

La condición `eRg.dO(short)` devuelve oculto cuando nivel ≤50 y visible desde 51. Se ejecutó con 1, 49, 50, 51, 60, 100 y 250. Esto explica por qué nivel 50 seguía bloqueado: no hace falta decidir otro umbral. El cliente usa niveles del roster en `cgY`, `biz.dqi` y la sección CHARACTERS; también consulta el estado `eDS.oUk` al entrar y cuando cambia. La lista y el bootstrap del servidor deben transmitir niveles coherentes; el salto por consola no actualiza por sí solo todos esos modelos.

## Cupo resuelto

`eQZ.fHr()` lee `eEL.pdS`: `NON_PERMANENT_BUILD_LIMIT`, configuración 2510, clave `non.permanent.build.limit`, default 24. `bhp.eH("countAndLimit")` muestra `eQW.fHo()/fHr`; `fHo` cuenta hojas **no permanentes**, no todos los índices. `eQS` contiene 16 tramos permanentes. Se crearon 24 hojas no permanentes en el modelo nativo y se seleccionó índice 3 correctamente. La guarda 0–2 del servidor no refleja ese catálogo.

La solución debe validar cantidad de hojas no permanentes por separado del rango e identidad de índices. No sustituir `index<=2` por `index<=24`: el contador no demuestra ese rango y el protocolo usa un byte con signo. Preservar predeterminada/permanentes y completar todas las colecciones.

## Respuesta de activación resuelta

`ctV.d()` devuelve **13811**. `ctV.dp` lee i64 de personaje y byte con signo del índice: **9 bytes**. El handler `ciu`, caso 13811, llama `eQX.R(id,index)` y actualiza la selección del modelo. Se probó cuerpo sintético ID 1/índice 3; sus getters devuelven esos valores. Un cuerpo de 8 bytes produce BufferUnderflowException. `dp` devuelve false también al decodificar el cuerpo válido; ese retorno no es un status de fracaso.

Esto completa el contrato de éxito que antes estaba sin investigar. 12837 sigue siendo borrado y 12284 guardado; no son ACK de activación. No inventar un campo status en 13811. El orden de refresh efectivo y recuperación ante rechazo debe probarse con el estado optimista real; la búsqueda de strings heroBuildLock no basta para asumir que activar usa el mismo bloqueo que guardar o borrar.

## Cambio concreto del plan

1. Resolver disponibilidad a partir de niveles autoritativos y umbral nativo 51; sincronizar roster/bootstrap al progresar.
2. Definir un catálogo único con clasificación permanente/no permanente, cupo configurable coherente con 2510 y todas las hojas registradas.
3. Decodificar 13776 como identidad e índice; validar ownership, lease, fase, existencia y revisión antes de mutar.
4. Persistir selección y revisión con la autoridad de builds. No activar implícitamente al guardar.
5. Emitir selección **13811** luego del commit, junto con refresh de efectos/hojas en orden verificado. Ensayar que el cliente converge, no solo que el decoder acepta bytes.
6. Reproducir rechazo y reconexión antes de declarar cerrado el flujo. La ejecución de hechizos/decks de combate queda a la otra sesión; no se modifica ni prueba aquí.

## Evidencia y límites

[Resultados estructurados](../34-builds-personalizadas/probe-politica-nativa.json). Los dumps y el probe compilado permanecen privados en .runtime. Se verificaron codecs y política nativa; la ruta 13776 del servidor aún no está implementada y esto no es una activación exitosa de extremo a extremo.

## Revalidación del código actual: selección y colecciones

Se ejecutaron las funciones actuales sin decks ni hechizos: `validate` acepta índices0/1/2 y rechaza3/24. Esto revalida la guarda incompatible con la selección nativa3, sin concluir que24 sea un índice permitido por el mero cupo.

Se construyó un personaje sintético con **build2 existente y guardada**, `active_build_index=2`, nivel100. `build_set` devuelve hojas0/1/2 pero su campo de selección sigue siendo **0**: la función escribe `proto_field(8,0)` e ignora la selección recibida. No se afirma que el servidor actual permita activar2 en vivo: falta handler13776; la prueba demuestra que añadir solo ese handler tampoco preservaría la selección en este carrier. La solución debe serializar la selección persistida validada y comprobar reconexión, además del ACK13811.

Sin hojas guardadas, metadata anuncia0/1 y equipment_registry solo0. Este desajuste conocido se mantiene en el código revalidado. Unificar el catálogo de hojas y poblar sus carriers antes de acreditar secundaria usable. [Resultados y hashes actuales](probe-carriers-actuales.json). Ninguna llamada ejecutó validación ni combate de hechizos.

## Persistencia y borrado: límites de la autoridad actual

Se inicializó una SQLite nueva temporal con `Store`: `characters` no contiene `active_build_index`; `character_builds` solo guarda identidad/índice y cuatro blobs. El dispatcher inspeccionado sigue sin13776. La selección activa que algunos cálculos consultan no tiene aún una ruta persistida en ese esquema. La prueba no modifica la DB ni los personajes en uso. [Esquema y hashes](probe-persistencia-seleccion.json).

La implementación concreta debe añadir **selección activa autoritativa y revisión** al estado de builds, cargarlas al reabrir, y hacer que validar hoja/existencia, cambiar selección y revisionar sean una operación indivisible bajo lease. En SQLite esto requiere migración y transacción; con journal Redis no basta escribir un campo en SQLite y dejar las hojas en otro estado: el envelope debe abarcar selección y hojas o definir recuperación verificable para ambos dominios. Probar pérdida de conexión después del commit antes del ACK y reinicio antes del flush.

`BuildJournal.flush` solo hace upserts de hojas presentes, no elimina filas de `character_builds`. Al implementar borrado, **retirar una hoja del estado Redis por sí solo dejaría su fila SQLite y podría resucitarla al recuperar**. Incorporar eliminación/tombstone revisionado en el flush con ownership y baseline; no borrar filas ajenas ni hoja permanente. Si se elimina la activa, persistir fallback y sus carriers en la misma transición, según regla nativa todavía por cotejar. Este es un defecto potencial del plan de integración, no una reproducción de borrado hoy disponible.

Guardar una hoja llama `effective_character(updated)` y recalcula salud tanto en Store como BuildJournal; no hay una selección persistida que distinga edición de secundaria de cambio activo. Antes de integrar activación hay que demostrar que **editar una hoja inactiva no cambia estadísticas/salud efectivas** y que activar utiliza equipo/aptitudes del índice elegido. No se congela una fórmula oficial de salud por intuición ni se ejecutan hechizos.

## Edición de secundaria y salud: caso ejecutado

Se ejecutó `Store.save_build` sobre SQLite desechable con personaje propio nivel6, salud41/110 y amuleto2021 no apilado en inventario. Guardar ese equipo en **hoja1** deja salud **41/110**; guardar el mismo equipo en **hoja0** deja **41/116**. Decks y aptitudes vacíos, sin ejecutar hechizos. La secundaria inactiva **no altera salud en este caso**; no presentar el riesgo anterior como fallo reproducido.

Esto acredita la selección implícita0 del cálculo y el aislamiento de la hoja1 para ese equipo. No acredita activación1, modulación, Redis, edición con porcentaje de salud, salud llena o recuperación tras reinicio. Conservar esta comprobación al implementar selección persistida y repetir con activa1/editada0 para detectar regresión inversa. [Resultados](probe-edicion-secundaria-salud.json).
