# Rendimiento: cotejo después de tus respuestas

## Qué se midió

No existe un objetivo impuesto de p95 ni una medición real de 20 segundos: ese número era un ejemplo del usuario. El objetivo es reducir latencia y accesos a disco en las rutas del servidor. [Trace SQL aislado](probe-sql-redis-actual.json): una lectura con hit Redis ejecuta 9 SELECT, 3 INSERT y 7 sentencias DDL; se repite tras el flush. Guardar una build ejecutó 20 SELECT, 6 INSERT, 2 UPDATE y 15 DDL. Los tiempos son de una fixture local, no de producción; los 228.955 ms del guardado incluyen inicialización fría y no acreditan una demora sostenida de combate.

## Qué demuestra el código

El journal de builds evita escrituras inmediatas de sus filas, pero la hidratación sigue pasando por SQL, schema y otros dominios. «Está en Redis» no equivale a «no accede a SQLite». Hay que separar lectura caliente, validación de sesión, catálogo y persistencia diferida, y mover el DDL a inicialización/migraciones.

La configuración de `compose.yaml` usa AOF con `appendfsync always` y deshabilita snapshots periódicos. Por tanto, las escrituras de Redis también pueden esperar disco. Redis documenta que `always` sincroniza antes de responder y que `everysec` usa sincronización en segundo plano con una ventana de pérdida ante fallo abrupto. [Persistencia oficial](https://redis.io/docs/latest/management/persistence/). Esto precisa la propuesta del usuario de persistencia periódica; no se ha cambiado la configuración ni ejecutado SAVE/BGSAVE.

## Referencia Dofus realmente cotejada

Se leyó `/Users/hectorpulido/dofus/ai-service/spell_catalog.py` exclusivamente como arquitectura de caché: `refresh` consulta Redis antes de SQL y publica un catálogo en memoria bajo lock. No se ejecutó ni modificó Dofus. Es una referencia para datos estáticos; no demuestra un journal de personajes ni garantiza atomicidad de recompensas de Wakemu. No se continúa ninguna revisión de hechizos de Wakemu.

## Shutdown y mejoras existentes

`local_game_server.stop` ya hace flush de posiciones/builds/grupos, marca STOPPING, drena conexiones, espera workers y vuelve a hacer flush. Hay que probar fallos y escrituras en vuelo, no proponer «añadir graceful shutdown» como si no existiera. La política de cierre debe abarcar todos los dominios pendientes, impedir nuevas mutaciones y verificar revisiones confirmadas.

El tick de salud cambió concurrentemente. Se ejecutaron los tres tests existentes de `test_health_tick_writes.py`: pasan, incluidos no-op de salud completa/muerto/detenido y generación reemplazada. Esto corrige una parte del diagnóstico antiguo; no elimina el SQL redundante de hidratación ni prueba Redis real.

## Trabajo concreto restante

Inventariar por dominio qué se mantiene en memoria, Redis y SQL; medir handler→cola→commit→escritura de socket con percentiles y conteos. Probar el journal con Redis real, reinicio de proceso y caída abrupta sobre datos exclusivos. Usar flush por revisiones y lotes para no borrar una mutación posterior al snapshot confirmado. La auditoría no certifica aún la latencia del conjunto ni autoriza cambios de configuración.
