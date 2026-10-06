# E07 — eliminación y journal (avance parcial)

Se identificó una brecha concreta: `BuildJournal.flush` solo insertaba/actualizaba hojas presentes. Una hoja retirada del snapshot Redis quedaba en SQL y podía reaparecer tras checkpoint/reconexión.

El flush ahora elimina índices presentes en el baseline SQL y ausentes del snapshot vigente, dentro de la misma transacción que las escrituras y después de comprobar identidad, ownership y baseline. Solo elimina `character_builds` del personaje correspondiente; no toca objetos de inventario.

Prueba: guardar/checkpoint una hoja, retirar del journal, flush, reabrir SQL y verificar ausencia y objeto intacto. Un segundo flush no vuelve a aplicar el cambio. Suite de journal/capacidad:36 casos, **23 PASS y13 SKIP** sin Redis real configurado en esta ejecución.

Pendiente: transición de borrado con lease, protección de permanentes, fallback de selección activa, handler/ACK nativos y aceptación visual. Esta prueba del mecanismo no autoriza al cliente a borrar la predeterminada; el handler deberá impedirlo.

## Contrato nativo de borrado implementado

Petición13169 (`cnO`): i64 actor + byte con signo de índice,9 bytes. `decode_deletion` rechaza truncados, bytes extra e identidad inválida. Respuesta12837 (`cnP`): actor/índice + byte **failed**,10 bytes. `cEN` libera el lock en ambas ramas; failed1 muestra error y failed0 llama `dbU.d` para borrar.

Se implementó `deletion_message` con argumento booleano `failed`, evitando confundir éxito y error. Probe nativo: **PASS native12837 actor=7 index=127 error=false/true**. Suite de capacidad/selección/codecs:11 pruebas PASS.

La mutación completa sigue pendiente: eliminación Redis y selección SQL pertenecen hoy a dominios distintos. Deben converger tras caída entre persistencias sin hoja activa ausente ni resurrección. No conectar un handler que anuncie éxito hasta resolver ese contrato, protección del catálogo y actualización de colecciones.

## Corte después del commit de eliminación

Se inyectó un fallo del checkpoint Redis después del commit SQL de la remoción. SQL queda sin la hoja; al reabrir Store+BuildJournal, la reconciliación detecta el commit terminado y avanza el baseline, sin resucitarla. El flush posterior no reaplica cambios.

Suite journal/capacidad:39 casos, **25 PASS y14 SKIP** sin URL de Redis real en este comando. La inyección prueba esa frontera concreta; no acredita todavía la eliminación de una build activa desde el cliente.

Seguimiento estructurado reconciliado con README: E04/E05/E07/E08/E10 son parciales, ninguno completo.
# Catálogo sin hojas implícitas recreadas

El catálogo publica ahora únicamente build0 permanente y hojas guardadas. Ya no inyecta build1 en metadata, registro de equipo o aptitudes. El cupo cuenta hojas no permanentes existentes, sin reservar una plaza fantasma. Los tests de activación crean explícitamente su hoja antes de seleccionarla; no se añadió compatibilidad con la selección de una hoja inexistente.

Suite builds/capacidad/journal/anillos/equipo:45 PASS y16 SKIP antes de añadir la regresión específica. Esta última elimina hoja1 del journal, comprueba ausencia en los tres registros, hace checkpoint y reabre SQL sin recrearla. Esto corrige un requisito previo de E07; siguen pendientes operación de borrado atómica con selección y handler13169. Cambios aún sin recargar en world.

Verificación adicional dentro de Docker con Redis aislado: suites capacidad/builds/journal/anillos/bootstrap/snapshot, **70 PASS y1 SKIP** (inyección de fallo exclusiva de MemoryRedis). Incluye la regresión de eliminación de hoja1 sin recreación y los cambios de nivel efectivo del actor. Redis temporal eliminado al terminar. No es una prueba del handler13169, que sigue pendiente. Para borrado activo, el estado actual exige coordinar la selección SQL con las hojas del journal Redis; no basta eliminar la hoja y cambiar la selección en dos commits independientes.

## Operación SQL de borrado

Implementado `Store.delete_build`: valida lease seleccionado y propiedad, rechaza combate/build0/hojas permanentes/inexistentes; elimina hoja, cambia selección activa a0 si corresponde, incrementa revisión y recalcula máximo/HP sin curar. Todo dentro de una transacción SQL; no elimina items. Regresión: hoja1 activa con7HP, borrado, selección0, mismo inventario, revisión+1, reapertura sin hoja1; replay rechaza. Suite capacidad: **13 PASS**.

La operación rechaza explícitamente un Store con journal configurado: no introduce fallback SQL ni pretende coordinar dos commits. Es la implementación del contrato transaccional SQL, que debe integrarse con el estado combinado de journal antes de habilitar13169 en world. Handler y transición Redis siguen pendientes; E07 no está resuelto ni desplegado.

## Fallos y restricciones de borrado

Un trigger de prueba aborta la escritura de salud después del DELETE de la hoja y del UPDATE de selección. Reabrir Store confirma rollback de hoja, índice activo, revisión, HP, máximo e inventario. También se comprueba rechazo de lease reemplazado y hoja permanente provisionada por servidor. Estos ensayos no usan el journal como fallback; la integración Redis continúa pendiente.

## Integración tras retirar el journal (PostgreSQL)

Los apartados anteriores de coordinación SQL/Redis documentan un diseño retirado por E01. La autoridad actual es PostgreSQL: delete_build confirma hoja, selección y salud en una transacción. Se conectó13169 en el dispatcher: propiedad, lease y fase se validan;12837 failed=true libera controles en rechazo y failed=false elimina la hoja nativamente. Después del ACK de éxito se envían selección13811 y estadísticas autoritativas. Peticiones malformadas reciben rechazo con identidad propia/índice activo válido, sin eliminar hojas. Repetir un índice inexistente devuelve rechazo, sin mutación adicional.

Contrato cotejado nuevamente contra cEN/cnP: el booleano representa error y cEN libera heroBuildLock antes de ambas ramas. No se altera el motor de hechizos. Handler aún sin desplegar; pruebas encargadas a Luna y aceptación visual pendiente.

### Pruebas del handler real

Luna ejecutó el branch AST real13169 con harness para evitar efectos del bootstrap. Suites test_build_capacity y test_builds: **30 pruebas pasan**. Cobertura: borrado activo/inactivo; orden12837→13811→13046; fallback0; inventario equipado intacto; actor ajeno; petición malformada; build0/permanente/inexistente; replay; combate; lease sustituido; rollback SQL. Errores de infraestructura no se anuncian como éxito ni se convierten a rechazo de negocio. Construcción/carga Docker en curso; aceptación visual pendiente.

Handler13169 cargado en el Docker principal tras build y recreación autorizados; world quedó healthy. Validación visual aún pendiente.
