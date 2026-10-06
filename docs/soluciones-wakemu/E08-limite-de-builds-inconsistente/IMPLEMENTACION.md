# E08 — revisión para implementación

Estado: revisión técnica en curso; límite aún no corregido.

## Brechas actuales comprobadas

- `items/builds.py:validate` y `blocked_save_messages` aceptan únicamente índices0–2.
- `storage/build_journal.py:_checked` exige claves textuales0/1/2, por lo que ampliar solo el validador rompe lectura y recuperación Redis.
- `build_set` publica selección0 y añade hojas0/1; `equipment_registry` registra0 y las guardadas. El catálogo debe unificarse antes de activar índices nuevos.
- El dispatcher aún carece de13776; guardar12772 sigue siendo un flujo distinto.

La implementación debe separar índice representable en el byte nativo, clasificación permanente y cupo24 no permanente. No usar24 como índice máximo ni aceptar flags de permanencia enviados por el cliente sin autoridad de catálogo. SQL, journal, bootstrap, respuesta y rechazo deben compartir esa política.

## Baseline ejecutado

`PYTHONPATH=server:server/tests python3 -m unittest server.tests.test_builds server.tests.test_build_journal server.tests.test_ring_build_integration -q`:32 casos, **22 PASS y10 SKIP**. Esto acredita el comportamiento cubierto actual, no activación13776 ni cupo ampliado. El primer intento sin `server/tests` en PYTHONPATH falló por imports de helpers; se corrigió el comando.

Se preserva el motor de hechizos de la otra sesión. No hay modificación funcional de builds en esta revisión.

## Cambio parcial implementado

`builds.valid_index` valida0–127 como IDs representables por el byte con signo nativo. Guardado y rechazo durante combate comparten esa guarda; el journal acepta claves decimales canónicas del mismo rango (rechaza01, negativos y128).

El cupo se valida contando hojas no permanentes, incluyendo Build1 publicada por bootstrap. Editar una de24 hojas es válido; crear una hoja adicional falla aunque tenga índice representable. Una petición no puede crear una hoja permanente para evadir el límite. El índice0 se considera predeterminado permanente.

Suite ampliada:34 casos, **24 PASS y10 SKIP**. Regresiones cubren índices dispersos, límite de byte, claves Redis canónicas, edición a cupo completo, hoja25 y permanencia falsa.

Pendiente antes de cerrar: parametrizar cupo en DB y sincronizarlo con configuración nativa, catálogo de hojas permanentes, persistencia/activación coherente y aceptación visual. Este cambio todavía no se cargó en Docker. No se declara resuelto E08 ni34.

## Cupo en DB y clasificación autoritativa

`settings.non_permanent_build_limit` se crea con default24 y se lee al cargar el personaje, tanto para guardar directamente como mediante journal. Rango admitido1–24: no habilitar más hojas que el cupo nativo acreditado. Valores inválidos fallan explícitamente. La sincronización del contador visual con valores menores que24 sigue pendiente.

La clasificación permanente de una hoja existente tampoco puede retirarse mediante guardado. Así se evita alterar el catálogo autoritativo desde metadata enviada por el cliente.

Suite con persistencia:46 casos, **36 PASS y10 SKIP**. Pruebas adicionales: modificación de cupo en DB, reapertura, rechazo de nueva hoja con cupo1, configuración inválida y protección de permanencia existente.

Pendientes vigentes: catálogo completo, activación/persistencia de selección y validación visual. El cupo del servidor ya está parametrizado; este avance sustituye ese pendiente del apartado anterior. No desplegado todavía.

## Consumidor de estadísticas

`equipment_stats.bonuses` también tenía una guarda0–2; ahora comparte `builds.valid_index`. Se ejecutó una regresión SQL real: guardar índice127 con metadata válida, reabrir Store y calcular bonificaciones de esa hoja.128 sigue rechazado.

Suite actual:47 casos, **37 PASS y10 SKIP**. Esto demuestra persistencia SQL del índice alto y lectura de estadísticas, no selección en cliente ni recuperación Redis real.

## Redis real aislado

Se ejecutaron las suites dentro de `world` con una instancia Redis temporal independiente, sin volúmenes y sin puertos publicados. No se utilizó el Redis del juego ni su namespace. Se eliminó el contenedor temporal al terminar.

Resultado:41 casos, **40 PASS y1 SKIP** (caso de inyección de fallo exclusivo del doble de memoria). La nueva regresión se ejecuta tanto con MemoryRedis como Redis real: guardar127 en el journal, verificar SQL aún vacío, reabrir desde otro Store con overlay y checkpoint a SQL; la reapertura SQL conserva exactamente la hoja.

Comando: `PYTHONPATH=/app:/tmp/wakemu-build-tests WAKFU_REDIS_TEST_URL=redis://wakemu-build-tests-redis:6379/0 python3 -m unittest test_build_capacity test_builds test_build_journal test_ring_build_integration -q` dentro de Docker. La prueba importó el código actual montado; el proceso del juego no se reinició ni se declara actualizado por ejecutar estos tests.

## Carrier de cupo identificado e integrado

Cotejo nativo: `cir` consume22318 (`cEp`), decodifica clave y valor como strings UTF-8 precedidos por longitud i32 y llama `eEI.a(eEL.tk(key), value)`. Este delta conserva otros ajustes;23053, por contraste, sustituye el mapa de configuración completo. `eQZ.fHr` lee el ajuste2510 `non.permanent.build.limit`.

Fixture Java offline delegada: body `000000196e6f6e2e7065726d616e656e742e6275696c642e6c696d69740000000131` decodificó límite1; el getter nativo cambió24→1 y `calendar.delta=7` se conservó. No se invocó la UI ni se modificó el cliente. Dumps privados en `.runtime/local/build-config-*.javap`; no se distribuyen jars.

`builds.capacity_message` serializa el límite leído desde PostgreSQL, validando entero1–24. El servidor lo envía antes del bootstrap23082, y después de guardar o rechazar una build usando el personaje recargado. No cambia decks ni hechizos. Esta ampliación está en fuente, pendiente de regresión/carga y contador visual; no se atribuye al contenedor actual. Los cambios de DB durante una sesión se anuncian al siguiente guardado o reentrada, no mediante push automático.

La regresión ampliada del carrier pasó en el gate PostgreSQL: **54 pruebas OK**, incluidas las dos pruebas de cuerpo exacto22318 para1/24 y rechazo de valores inválidos. La imagen se está construyendo; aceptación visual pendiente.

## Carga comprobada del cupo

Imagen `62a9b743aac46ca1e7f14b469f5267e807b17a5be8624aaa4ebda5803843b233` cargada; world healthy y `/health` PostgreSQL ok. Los54 tests y la fixture nativa acreditan encoder/getter; el contador visual y catálogo permanente siguen pendientes.
