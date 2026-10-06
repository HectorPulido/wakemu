# Parámetros del servidor en base de datos

## Requisito del usuario

Cooldowns y demás reglas configurables de juego deben residir en la base de datos, incluyendo los ajustes de la captura de Compose. Este requisito amplía los issues 1, 2–10, 18, 20, 28, 29 y 32. Es una propuesta auditada, no una migración implementada.

## Correspondencia con la configuración actual

| Variables actuales | Destino propuesto |
| --- | --- |
| `WAKFU_ALL_ZAAPS`, `WAKFU_ALL_DRAGOS`, `WAKFU_OPEN_PLANTING` | Políticas de desbloqueo de transportes y autorización de plantación. |
| `WAKFU_PLANT_GROWTH_SECONDS`, `WAKFU_LOCAL_MONSTER_RESPAWN_SECONDS` | Tiempos de crecimiento y repoblación; reglas por especie/recurso/zona. |
| `WAKFU_MAX_CHARACTERS` | Límite de personajes por cuenta. |
| `WAKFU_LOCAL_FIGHT_XP`, `WAKFU_LOCAL_FIGHT_KAMAS` | Política de recompensas; sustituir importes fijos por fórmulas y multiplicadores de XP, kamas y drop versionados. |
| `WAKFU_COMBAT_ARENA_RADIUS` | Política de construcción del terreno; validar cobertura y colocación antes de publicar un valor. |
| `WAKFU_ENABLE_COMBAT_TEST`, `WAKFU_COMBAT_TEST_GROUP_SIZE`, `WAKFU_COMBAT_TEST_WP` | Perfil de pruebas explícito en DB, separado de las reglas normales; WP vacío significa recurso nativo, no cero. |
| `WAKFU_COMBAT_START_EVENTS`, `WAKFU_NATIVE_AREA_CALLBACKS` | Capacidades del servidor versionadas; comprobar dependencias. Los hechizos los revisa otra sesión. |
| `WAKFU_POSITION_FLUSH_SECONDS`, `WAKFU_CLOCK_OFFSET_SECONDS`, `WAKFU_EXTERNAL_SCHEDULER` | Ajustes operativos: persistencia, reloj simulado y autoridad del scheduler. Mantener su separación de las reglas de juego aunque se administren en DB. |

Añadir también cooldown de extracción por criatura/acción, duración de recolección, probabilidad de plantación, movimiento cada 5 s con probabilidad 25% y pasos aleatorios, reproducción, límites de población, activación de zonas y multiplicadores de mazmorras. No inventar valores oficiales para reglas todavía no acreditadas.

`WAKFU_AI_URL`, `WAKFU_REDIS_URL`, host anunciado y puertos son configuración de conexión y arranque. Conservarlos en entorno/configuración de despliegue: el servidor necesita conocer sus dependencias antes de cargar políticas. La captura no convierte esos endpoints en reglas de juego.

## Diseño concreto propuesto

Crear mediante migración `server_policy_versions(id, status, created_at, created_by)` y `server_policy_values(version_id, key, scope_type, scope_id, value_json)`, con unicidad por versión, clave y ámbito. Un registro de claves en código valida tipo, unidad, rango, valores permitidos y política de recarga; rechazar claves desconocidas. Ámbitos global, mapa, especie/recurso y acción, con precedencia documentada y sin ambigüedad.

Publicar una versión completa atómicamente después de validar todas sus dependencias. SQL es la fuente persistente; Redis mantiene snapshots versionados. Cargar una vez por revisión y compartir el snapshot en memoria, sin consultar DB por movimiento o tirada. Registrar revisión efectiva en logs y recibos. No permitir que variables antiguas sobrescriban silenciosamente la DB; los overrides de pruebas deben ser explícitos, aislados y visibles.

Congelar política al iniciar combate/recompensa o reservar una recolección: cambiar un multiplicador o cooldown no debe alterar una operación en curso ni volver a entregar una recompensa. Persistir además la disponibilidad de la criatura; guardar solo la duración del cooldown no evita que se reinicie al reconectar. Cambios de scheduler y persistencia requieren un traspaso controlado, sin dos workers activos ni pérdida de mutaciones pendientes.

## Evidencia y validación pendiente

Cotejado con `compose.yaml`, inicialización de `server/local_game_server.py`, `combat/combat_lifecycle.py::policy_from_env` y `combat/combat_terrain.py::local_arena`: actualmente se leen variables de entorno, algunas al arrancar y otras por operación. El cooldown de extracción sigue pasado como literal cero; véase el probe del issue 1.

La futura implementación debe probar tipos/rangos, precedencia, actualización concurrente, rollback, caché obsoleta, caída de Redis, reinicio, lectura consistente por varios procesos y ausencia de doble premio. Cambiar una regla en DB debe afectar nuevas operaciones sin editar Compose; las operaciones existentes conservan su revisión. No se cambiaron código, Compose ni bases de datos.

## Avance de implementación PostgreSQL

La configuración aún no está migrada por completo.006 incorpora
`settings.monster_wander` (5s,25%, pasos1–3 y radio20), cargada y con14 pruebas
dirigidas;008 incorpora `settings.monster_harvest` (cantidad1 y cooldown60s),
en validación antes de carga. El cooldown se comprueba contra recibos
por mapa/instancia/criatura/acción, antes de iniciar y dentro de la entrega
transaccional. La política de extracción se congela en el ticket; cambios en DB
afectan solicitudes nuevas. Los valores iniciales son políticas locales.
El diseño transversal de versiones y ámbitos sigue pendiente; estas dos claves
no acreditan la migración de las demás variables de Compose.

## Estado verificado el 6 de octubre

Las referencias anteriores a cooldown cero y008 sin cargar son históricas.006 y008 están aplicadas: movimiento y recolección leen sus políticas de PostgreSQL.011 añade un deadline persistido por recibo, conservado aunque cambie la duración de la política; el gate actualizado de43 pruebas cubre restauración, nuevos tickets, respawn y cleanup. El usuario acreditó recolección, botón deshabilitado durante regeneración y reapertura tras el cooldown.010 agrega políticas de monturas (habilitadas y sin misión por defecto; cooldown de montaje1000ms como política local), con19 pruebas de autoridad/codec, pero el handler de montaje continúa pendiente. Esto no completa la migración de las demás variables de Compose ni el diseño de versiones y ámbitos.
