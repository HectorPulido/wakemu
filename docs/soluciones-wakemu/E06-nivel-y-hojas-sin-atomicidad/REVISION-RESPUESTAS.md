# E06 — Nivel y hojas sin atomicidad

## Causa cotejada

`test_console.execute`, rama `!nivel`, abre BEGIN IMMEDIATE, valida lease y confirma nivel/XP. Solo después de salir de esa transacción llama a `health_store.initialize`; luego construye la notificación. Un fallo de validación o almacenamiento posterior no revierte el nivel ya confirmado. El historial 49→50 con hoja fija incompatible describe una manifestación concreta; no se atribuye toda subida normal de XP a este comando administrativo.

`aptitudes.validate` acepta nivel de hoja −1 o exactamente `character.level`; rechaza una hoja fija anterior al nuevo nivel. Esta restricción explica el riesgo al hidratar hojas guardadas o journal después de confirmar nivel. La semántica de nivel modulado necesita el modelo de build activa del issue 34; no se debe reemplazar indiscriminadamente todo nivel fijo por −1.

## Reproducción del estado parcial actual

[Probe y hash](probe-fallo-entre-transacciones.json): SQLite desechable, personaje nuevo nivel 1, 50/50 HP. Se inyectó un fallo en la llamada posterior de inicialización de salud, antes de serializar notificaciones. `!nivel 50` propagó ValueError, pero SQL conservó nivel **50**, XP **8.809.696** y salud **50/50**. Demuestra el límite transaccional actual sin ejecutar hechizos, usar GUI o tocar jugadores reales. El fallo fue inducido: no afirma una nueva incidencia espontánea en el servidor vivo.

## Solución concreta del servidor

Preparar el estado propuesto de nivel, XP, presupuestos de aptitudes y salud desde un snapshot autoritativo antes de confirmar. Validar coherencia de todas las hojas afectadas, diferenciando hojas de nivel actual y hojas moduladas. Reutilizar una sola conexión/transacción para nivel/progresión/salud/regeneración; los servicios deben aceptar contexto transaccional sin commits independientes. Emitir notificaciones solo después de commit.

Con journal Redis, no validar contra SQL antiguo ignorando hojas pendientes. La transición debe declarar una única revisión de personaje/build y un recibo durable. Si se usa autoridad Redis con flush diferido, nivel y hojas necesitan una operación atómica en esa autoridad; no simular atomicidad entre Redis y SQLite mediante dos writes sucesivos. Comparar revisión/lease al confirmar y conservar cambios concurrentes de otras sesiones.

Definir salud para personaje sano y herido, sin curación accidental por alternar hojas (E12). Al recuperar un estado parcial histórico, conservar XP legítima y referencias de inventario; recalcular salud y presupuestos de forma idempotente, registrando qué se cambió. No borrar puntos o hojas para ocultar el error. Una migración requiere copia y diagnóstico de cada inconsistencia antes de aplicarse.

## Verificaciones restantes

El caso natural fijo frente a −1 ya se repitió abajo; falta el caso de build modulada válida. Probar fallo antes del commit, después del commit/antes del ACK, sesión sustituida, journal pendiente, conflicto concurrente y reintento. Revisar subida por recompensas separadamente para no extender sin evidencia el resultado del comando administrativo. No se implementó ninguna corrección.

## Caso natural 49→50 reproducido de nuevo

[Resultados](probe-hoja-fija-49-a-50.json): dos personajes nuevos en SQLite desechable, nivel 49 y salud 540/540. Se validó primero el protobuf de aptitudes al nivel 49 y se insertó la hoja directamente para evitar serialización de decks ajena a este alcance. Con nivel de hoja **49**, `!nivel 50` produjo **Invalid aptitude sheet level** y SQL quedó nivel **50**, salud **540/540**. Con la misma hoja vacía pero nivel **−1**, el comando completó y quedó nivel **50**, salud **550/550**.

Esto reproduce la incompatibilidad real de validación, sin inyectar un fallo de salud. No demuestra cómo una hoja fija llegó a guardarse mediante GUI ni prueba builds moduladas; la fixture representa un estado que el validador acepta al nivel inicial. El cambio necesario debe resolver ese estado de forma explícita antes del commit, no convertir automáticamente cualquier hoja modulada en nivel corriente. No se tocaron jugadores ni hechizos.

## Contraste con recompensas de combate

[Probe de recompensa](probe-recompensa-hoja-fija.json): combate sintético ya terminado, sin ejecutar turnos ni hechizos; personaje nivel 49 con hoja fija 49. `award` confirmó conjuntamente XP para nivel 50, 17 kamas y un recibo. La salud quedó 540/540; calcular estadísticas efectivas después falló con `Invalid aptitude sheet level`. Esto amplía la evidencia a recompensas: el premio es transaccional, pero no valida ni transforma hojas para el nuevo nivel. No se probó el retorno gráfico 12925 ni pérdida del premio; sus datos sí quedaron persistidos. La solución debe incluir coherencia de hojas en la preparación del premio, no limitarse a cambiar el comando administrativo.

## Confirmación Redis y rollback SQL: frontera reproducida

[Probe de fallo entre autoridades](probe-cas-redis-y-rollback-sql.json): `BuildJournal.save` confirmó una hoja de10 puntos HP en MemoryRedis y después se indujo una excepción en `health_store.schema`, tras UPDATE de salud pero antes del commit SQL. SQL revirtió y quedó **1050/1050**, cero filas de builds; Redis conservó la hoja pendiente de índice0. El save devolvió error, pero una parte de la operación permanece en el journal. No hay rollback automático del CAS Redis por el contexto SQLite.

No es pérdida de puntos ni doble objeto probados: demuestra dos autoridades con confirmaciones independientes. Tampoco se equipara MemoryRedis con durabilidad AOF real. La recuperación debe usar recibo/revisión común para completar salud y hoja o impedir exposición de una transición incompleta; no borrar el registro Redis a ciegas, porque podría contener una edición posterior. Un retry tiene que distinguir operación parcialmente confirmada de nueva edición y conservar fencing de sesión. No se implementó la reparación.
